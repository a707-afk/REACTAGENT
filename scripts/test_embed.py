import os, sys
os.environ['INFERENCE_DEVICE'] = 'cuda'
sys.path.insert(0, os.getcwd())
from app.embeddings import get_embedding_model
print("Loading model...", flush=True)
m = get_embedding_model()
print(f"Model type: {type(m).__name__}", flush=True)
print(f"Has batch: {hasattr(m, 'get_text_embedding_batch')}", flush=True)
e = m.get_text_embedding_batch(['hello world', 'goodbye moon'])
print(f"Embed shape: {len(e)} x {len(e[0])}", flush=True)
print("Done!", flush=True)
