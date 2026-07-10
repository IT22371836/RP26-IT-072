#!/usr/bin/env python3
"""
Download the all-minilm-l6-v2 BERT model from Hugging Face
"""

from transformers import AutoModel, AutoTokenizer
import os

def download_model():
    model_name = "sentence-transformers/all-minilm-l6-v2"
    cache_dir = os.path.join(os.path.dirname(__file__), "models")
    
    print(f"Downloading {model_name}...")
    print(f"Cache directory: {cache_dir}")
    
    # Download tokenizer
    print("\nDownloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
    print("✓ Tokenizer downloaded")
    
    # Download model
    print("\nDownloading model...")
    model = AutoModel.from_pretrained(model_name, cache_dir=cache_dir)
    print("✓ Model downloaded")
    
    print(f"\n✓ Success! Model saved to: {cache_dir}")
    print(f"Model name: {model_name}")
    print(f"Model size: ~22.7 MB")

if __name__ == "__main__":
    download_model()
