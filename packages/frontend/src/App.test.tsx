import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import App from "./App";

describe("authentication entry flow", () => {
  beforeEach(() => localStorage.clear());

  it("shows sign in by default and allows switching to registration", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /I need a service/ })).toBeInTheDocument();
  });
});
