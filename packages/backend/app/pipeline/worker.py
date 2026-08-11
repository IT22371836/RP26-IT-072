from __future__ import annotations

import asyncio
import contextlib
import logging
from time import perf_counter
from typing import Any

from app.components.component1.service import get_recommendation_engine
from app.components.component2.schemas import Component2FilterRequest
from app.components.component2.service import Component2FilteringService
from app.components.component4.schemas import Component4RankRequest
from app.components.component4.service import Component4RankingOrchestrator, get_component4_engine
from app.core.config import Settings, get_settings
from app.core.database import MongoDatabase
from app.integrations.firebase_component2 import (
    FirebaseComponent2Error,
    FirebaseRtdbClient,
    booking_history_preference_ids,
    merge_verified_provider_candidates,
)
from app.pipeline.schemas import PipelineStatus
from app.repositories.component1 import Component1Repository
from app.repositories.component4 import Component4Repository
from app.repositories.indexes import ensure_application_indexes
from app.repositories.interactions import InteractionRepository
from app.repositories.pipeline import PipelineRepository
from app.repositories.providers import ProviderRepository
from app.repositories.users import UserRepository
from app.schemas.common import new_public_id, utc_now

LOGGER = logging.getLogger("weda.pipeline.worker")


class PipelineExecutionError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class PipelineWorker:
    def __init__(self, database: Any, settings: Settings) -> None:
        self.database = database
        self.settings = settings
        self.pipeline = PipelineRepository(database)
        self.providers = ProviderRepository(database)
        self.users = UserRepository(database)
        self.interactions = InteractionRepository(database)
        self.component1_runs = Component1Repository(database)
        self.component4_runs = Component4Repository(database)
        self.firebase = FirebaseRtdbClient(settings)

    async def _heartbeat(self, run_id: str) -> None:
        interval = max(10, self.settings.pipeline_lease_seconds // 3)
        while True:
            await asyncio.sleep(interval)
            await self.pipeline.worker_heartbeat(
                self.settings.pipeline_worker_id, active_run_id=run_id
            )
            if not await self.pipeline.heartbeat(
                run_id,
                self.settings.pipeline_worker_id,
                self.settings.pipeline_lease_seconds,
            ):
                return

    async def run_once(self) -> bool:
        await self.pipeline.worker_heartbeat(self.settings.pipeline_worker_id)
        document = await self.pipeline.claim_next(
            self.settings.pipeline_worker_id,
            self.settings.pipeline_lease_seconds,
        )
        if document is None:
            return False
        run_id = str(document["run_id"])
        await self.pipeline.worker_heartbeat(
            self.settings.pipeline_worker_id, active_run_id=run_id
        )
        heartbeat = asyncio.create_task(self._heartbeat(run_id))
        try:
            await self._execute(document)
        except PipelineExecutionError as error:
            LOGGER.exception("Pipeline %s failed: %s", run_id, error)
            await self.pipeline.fail(
                run_id,
                self.settings.pipeline_worker_id,
                code=error.code,
                message=str(error),
                retryable=error.retryable,
            )
        except Exception as error:
            LOGGER.exception("Pipeline %s failed unexpectedly", run_id)
            await self.pipeline.fail(
                run_id,
                self.settings.pipeline_worker_id,
                code="model_failure",
                message=str(error),
                retryable=True,
            )
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
            await self.pipeline.worker_heartbeat(self.settings.pipeline_worker_id)
        return True

    async def _execute(self, run: dict[str, Any]) -> None:
        run_id = str(run["run_id"])
        request_id = str(run["request_id"])
        user_id = str(run["user_id"])
        request = dict(run["request"])

        component1 = run.get("component1")
        if not isinstance(component1, dict) or len(component1.get("providers", [])) != 20:
            LOGGER.info("Pipeline %s: Component 1 started", run_id)
            await self.pipeline.transition(
                run_id, self.settings.pipeline_worker_id, PipelineStatus.COMPONENT1_RUNNING
            )
            component1 = await self._run_component1(run_id, request_id, user_id, request)
            run = await self.pipeline.transition(
                run_id,
                self.settings.pipeline_worker_id,
                PipelineStatus.COMPONENT1_COMPLETED,
                {"component1": component1},
            )
            LOGGER.info(
                "Pipeline %s: Component 1 completed model=%s providers=%d",
                run_id,
                component1["model_version"],
                len(component1["providers"]),
            )

        component2 = run.get("component2")
        if not isinstance(component2, dict):
            LOGGER.info("Pipeline %s: Component 2 started", run_id)
            await self.pipeline.transition(
                run_id, self.settings.pipeline_worker_id, PipelineStatus.COMPONENT2_RUNNING
            )
            component2 = await self._run_component2(
                run_id, request_id, user_id, request, component1
            )
            run = await self.pipeline.transition(
                run_id,
                self.settings.pipeline_worker_id,
                PipelineStatus.COMPONENT2_COMPLETED,
                {"component2": component2},
            )
            LOGGER.info(
                "Pipeline %s: Component 2 completed model=%s providers=%d",
                run_id,
                component2["model_version"],
                len(component2["output_results"].get("provider_ids", [])),
            )

        c1_ids = [item["provider_id"] for item in component1["providers"]]
        c2_ids = list(component2["output_results"].get("provider_ids", []))
        if len(c2_ids) != len(set(c2_ids)) or not set(c2_ids).issubset(c1_ids):
            raise PipelineExecutionError(
                "invalid_subset",
                "Component 2 provider IDs must be unique and a subset of Component 1",
                retryable=False,
            )
        if len(c2_ids) > 10:
            raise PipelineExecutionError(
                "invalid_subset", "Component 2 returned more than ten providers", retryable=False
            )

        fallback = None
        source = "component2"
        c4_ids = c2_ids
        if not c2_ids:
            source = "component2_zero_fallback"
            c4_ids = c1_ids[:10]
            fallback = {
                "used": True,
                "source": source,
                "fallback_reason": "component2_returned_zero",
                "provider_ids": c4_ids,
            }

        component4 = run.get("component4")
        if not isinstance(component4, dict):
            LOGGER.info("Pipeline %s: Component 4 started source=%s", run_id, source)
            await self.pipeline.transition(
                run_id, self.settings.pipeline_worker_id, PipelineStatus.COMPONENT4_RUNNING
            )
            component4 = await self._run_component4(
                request_id,
                user_id,
                c4_ids,
                source,
                component1["providers"],
            )

        final_ids = [item["provider_id"] for item in component4["providers"]]
        if not set(final_ids).issubset(c4_ids) or len(final_ids) > 5:
            raise PipelineExecutionError(
                "invalid_subset",
                "Component 4 output is not a valid subset of its input",
                retryable=False,
            )
        await self.pipeline.transition(
            run_id,
            self.settings.pipeline_worker_id,
            PipelineStatus.COMPLETED,
            {
                "component4": component4,
                "fallback": fallback,
                "lease_expires_at": None,
            },
        )
        LOGGER.info(
            "Pipeline %s: completed Component 1=%d Component 2=%d Component 4=%d",
            run_id,
            len(c1_ids),
            len(c2_ids),
            len(final_ids),
        )

    async def _run_component1(
        self,
        run_id: str,
        request_id: str,
        user_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        engine = get_recommendation_engine(self.settings.component1_artifact_dir)
        if not engine.ready:
            raise PipelineExecutionError(
                "component1_model_failure", "Component 1 artifacts are unavailable", retryable=True
            )
        started_at = utc_now()
        started = perf_counter()
        try:
            mongo_providers, firebase_providers = await asyncio.gather(
                self.providers.list_all(limit=10_000),
                self.firebase.get_verified_provider_candidates(),
            )
        except FirebaseComponent2Error as error:
            raise PipelineExecutionError(
                "firebase_failure", str(error), retryable=True
            ) from error
        artifact_provider_ids = {
            str(provider["provider_id"]) for provider in engine.providers
        }
        live_providers = merge_verified_provider_candidates(
            artifact_provider_ids,
            mongo_providers,
            firebase_providers,
        )
        user = await self.users.find_by_id(user_id)
        firebase_uid = (user or {}).get("legacy", {}).get("firebase_uid")
        if not firebase_uid:
            raise PipelineExecutionError(
                "identity_failure",
                "Customer account has no Firebase booking-history identity",
                retryable=False,
            )
        try:
            booking_history = await self.firebase.get_customer_booking_history(firebase_uid)
        except FirebaseComponent2Error as error:
            raise PipelineExecutionError(
                "firebase_failure", str(error), retryable=True
            ) from error
        clicks = await self.interactions.click_preference_provider_ids(user_id)
        preferences = [*booking_history_preference_ids(booking_history), *clicks]
        results = await asyncio.to_thread(
            engine.recommend,
            request["request_text"],
            user_id,
            20,
            request["category"],
            request["district"],
            request["city"],
            0.0,
            live_providers,
            preferences,
        )
        if len(results) != 20:
            raise PipelineExecutionError(
                "component1_model_failure",
                f"Component 1 returned {len(results)} providers; exactly 20 are required",
                retryable=False,
            )
        finished = utc_now()
        processing_time_ms = round((perf_counter() - started) * 1000, 3)
        providers = [
            {**result.model_dump(mode="json"), "rank": rank}
            for rank, result in enumerate(results, start=1)
        ]
        component_run_id = f"C1-{run_id}"
        await self.component1_runs.persist_completed(
            {
                "run_id": component_run_id,
                "pipeline_run_id": run_id,
                "request_id": request_id,
                "user_id": user_id,
                "query": request["request_text"],
                "filters": {
                    "category": request["category"],
                    "district": request["district"],
                    "city": request["city"],
                },
                "requested_top_k": 20,
                "output_count": 20,
                "component_version": engine.manifest["component_version"],
                "model_version": engine.manifest["model_version"],
                "processing_time_ms": processing_time_ms,
                "started_at": started_at,
            },
            [
                {
                    "run_id": component_run_id,
                    "pipeline_run_id": run_id,
                    "request_id": request_id,
                    "user_id": user_id,
                    **provider,
                    "component_version": engine.manifest["component_version"],
                    "model_version": engine.manifest["model_version"],
                    "created_at": finished,
                }
                for provider in providers
            ],
        )
        await self.interactions.create_many(
            [
                {
                    "interaction_id": new_public_id("I"),
                    "request_id": request_id,
                    "pipeline_run_id": run_id,
                    "user_id": user_id,
                    "provider_id": provider["provider_id"],
                    "provider_name": provider["provider_name"],
                    "category": provider["category"],
                    "interaction_type": "impression",
                    "rating": None,
                    "timestamp": finished,
                }
                for provider in providers
            ]
        )
        return {
            "run_id": component_run_id,
            "engine": "hybrid_tfidf_semantic_cf",
            "model_loaded": True,
            "component_version": engine.manifest["component_version"],
            "model_version": engine.manifest["model_version"],
            "artifact_provider_count": engine.status()["provider_count"],
            "mongo_provider_count": len(mongo_providers),
            "verified_firebase_provider_count": len(firebase_providers),
            "additional_verified_provider_count": len(live_providers),
            "candidate_pool_count": len(artifact_provider_ids) + len(live_providers),
            "candidate_source": "artifact_plus_verified_live_providers",
            "preference_signal_count": len(preferences),
            "processing_time_ms": processing_time_ms,
            "started_at": started_at.isoformat(),
            "completed_at": finished.isoformat(),
            "providers": providers,
        }

    async def _run_component2(
        self,
        run_id: str,
        request_id: str,
        user_id: str,
        request: dict[str, Any],
        component1: dict[str, Any],
    ) -> dict[str, Any]:
        started_at = utc_now()
        started = perf_counter()
        user = await self.users.find_by_id(user_id)
        firebase_uid = (user or {}).get("legacy", {}).get("firebase_uid")
        if not firebase_uid:
            raise PipelineExecutionError(
                "identity_failure",
                "Customer account is not linked to Firebase",
                retryable=False,
            )
        provider_ids = [item["provider_id"] for item in component1["providers"]]
        payload = Component2FilterRequest.model_validate(
            {
                "request_id": request_id,
                "user_id": firebase_uid,
                "location_type": request["location_type"],
                "service_date": request["service_date"],
                "service_time": request["service_time"],
                "isNewRequest": True,
                "results": {"provider_ids": provider_ids},
                "pipeline": {
                    "run_id": run_id,
                    "component1_version": component1["component_version"],
                    "component1_model_version": component1["model_version"],
                    "component2_version": self.settings.pipeline_component2_version,
                    "component2_model_version": self.settings.pipeline_component2_model_version,
                    "worker_claim": self.settings.pipeline_worker_id,
                    "attempt_count": 1,
                    "created_at": utc_now().isoformat(),
                },
            }
        )
        firebase_payload = payload.model_dump(mode="json")
        try:
            await self.firebase.create_filter_request(request_id, firebase_payload)
            stored = await self.firebase.get_filter_request(request_id)
            if stored is None:
                raise FirebaseComponent2Error("Firebase request disappeared after creation")
            trusted_payload = Component2FilterRequest.model_validate(stored)
            customer, providers = await asyncio.gather(
                self.firebase.get_customer(firebase_uid),
                self.firebase.get_providers(provider_ids),
            )
            if customer is None:
                raise PipelineExecutionError(
                    "identity_failure",
                    "Linked customer has no Firebase customer profile",
                    retryable=False,
                )
            service = Component2FilteringService(
                component_version=self.settings.pipeline_component2_version,
                model_version=self.settings.pipeline_component2_model_version,
                weather_timeout_seconds=self.settings.pipeline_weather_timeout_seconds,
                weather_retries=self.settings.pipeline_weather_retries,
            )
            result = await asyncio.to_thread(service.filter, trusted_payload, customer, providers)
            completed_at = utc_now()
            await self.firebase.complete_filter_request(
                request_id,
                output_results=result.output_results,
                pipeline_updates={
                    "completed_at": completed_at.isoformat(),
                    "component2_version": result.component_version,
                    "component2_model_version": result.model_version,
                    "errors": None,
                },
            )
        except PipelineExecutionError:
            raise
        except FirebaseComponent2Error as error:
            raise PipelineExecutionError("firebase_failure", str(error), retryable=True) from error
        return {
            **result.model_dump(mode="json"),
            "engine": "deterministic_distance_hours_weather_filter",
            "processing_time_ms": round((perf_counter() - started) * 1000, 3),
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "firebase_request_id": request_id,
        }

    async def _run_component4(
        self,
        request_id: str,
        user_id: str,
        provider_ids: list[str],
        source: str,
        component1_providers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        started_at = utc_now()
        started = perf_counter()
        engine = get_component4_engine(
            self.settings.component4_artifact_dir,
            self.settings.component4_category_priors_path,
        )
        payload = Component4RankRequest(
            source=source,
            request_id=request_id,
            user_id=user_id,
            component_version=self.settings.pipeline_component2_version,
            model_version=self.settings.pipeline_component2_model_version,
            provider_ids=provider_ids,
            top_k=5,
        )
        selected = set(provider_ids)
        live_index = {
            str(provider["provider_id"]): dict(provider)
            for provider in component1_providers
            if str(provider.get("provider_id")) in selected
        }
        for provider in await self.providers.list_by_ids(provider_ids):
            provider_id = str(provider.get("provider_id") or "")
            if provider_id in selected:
                live_index[provider_id] = {**live_index.get(provider_id, {}), **provider}
        live_providers = list(live_index.values())
        response = await Component4RankingOrchestrator(engine, self.component4_runs).rank(
            payload,
            user_id=user_id,
            live_providers=live_providers,
        )
        completed_at = utc_now()
        return {
            **response.model_dump(mode="json"),
            "engine": "catf_precomputed_absa_credibility_ranking",
            "model_loaded": True,
            "pipeline_processing_time_ms": round((perf_counter() - started) * 1000, 3),
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        }


async def run_forever() -> None:
    settings = get_settings()
    await MongoDatabase.connect(settings)
    await ensure_application_indexes(MongoDatabase.get_database())
    worker = PipelineWorker(MongoDatabase.get_database(), settings)
    LOGGER.info("Pipeline worker %s started", settings.pipeline_worker_id)
    try:
        while True:
            if not await worker.run_once():
                await asyncio.sleep(settings.pipeline_poll_interval_seconds)
    finally:
        await MongoDatabase.disconnect()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
