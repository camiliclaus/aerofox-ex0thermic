# Independent model runtime

AeroFox 1.1.1 selects Qwen3-4B Q4_K_M with the llama.cpp b8230 Vulkan build when the Windows launcher detects a supported NVIDIA GPU with about 6 GB of VRAM. The tested RTX 3050 allocated about 3.86 GB with an 8,192-token context and a single slot. CPU-only machines use Qwen2.5-1.5B-Instruct Q4_K_M, with a separate quality and latency profile. The pinned files and SHA-256 digests are in scripts/local_model.py. The GPU model is about 2.50 GB, and the CPU model about 1.12 GB. Use Windows x64 and Python 3.11 or 3.12. The first run needs internet access. Questions use local inference and the local NASA snapshot thereafter.

    .\START_AEROFOX.bat

The launcher opens the web app when it is ready. Pass --offline for a deliberate evidence-only session or --external-local-model for an already running loopback service. The current mode appears on every answer and /api/health distinguishes configuration from readiness.

On Linux or macOS, obtain a compatible llama.cpp b8230 build from the official release or build that tag. Obtain the GGUF file from the pinned model revision. Match the SHA-256 values in scripts/local_model.py. Start llama-server as follows.

    llama-server --model /path/to/qwen2.5-1.5b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 8793 --alias aerofox-qwen-1.5b -c 8192 -np 1 -t 6 --log-disable
    sh ./start_aerofox.sh --external-local-model

The interface sends messages to the Python service. The Python service asks the model for a small typed tool plan and then supplies verified scientific tool summaries for a generated answer. Figures, numerical inputs, calculations and downloads use deterministic Python results. The UI identifies any fallback. There is a queue of one running generation and at most two waiters. A bounded queue, per-call deadline and daily turn quota protect the demo.

[Qwen model card and Apache-2.0 license](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9) · [llama.cpp b8230](https://github.com/ggml-org/llama.cpp/releases/tag/b8230)

Qwen3-4B and Qwen2.5-1.5B packages are Apache-2.0. The 8B Q4 variant uses most of a 6 GB GPU for model weights alone, leaving less headroom for context and compute buffers. The verified profile uses Vulkan and disables extended reasoning with the pinned runtime. Gemma 3 is an alternative architecture under the separate Gemma terms. Scores from a different AeroFox repository or an offline run are excluded from the migrated model benchmark. Ollama provides local models and native tools. The direct llama.cpp service gives this app an explicit GBNF plan constraint and permits the artifact hashes and Windows binaries to be pinned. Hosted GPU and Colab are optional experimental environments.

