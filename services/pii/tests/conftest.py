import os

# Set deterministic auth before app import.
os.environ.setdefault("API_KEY", "test-key-not-a-real-secret")
