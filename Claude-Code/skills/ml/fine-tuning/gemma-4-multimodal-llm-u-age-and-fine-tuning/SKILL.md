---
name: gemma-4-multimodal-llm-u-age-and-fine-tuning
description: Describes how to utilize, deploy, and fine-tune the Gemma 4 advanced
  multimodal large language models locally and on cloud platforms. Covers architectures,
  inference pipelines, integration with libraries (transformers, llama.cpp, mistral.rs,
  MLX), and fine-tuning techniques with TRL and Vertex AI. Use when building or adapting
  AI agents, multimodal applications, or fine-tuning Gemma 4 models for production
  or research.
artifact_type: skill
domain_path: ml/fine-tuning
source_urls:
- https://huggingface.co/blog/gemma4
brain_entry: Entries/2026-04-09-welcome-gemma-4-frontier-multimodal-intelligence-on-device
---

# Welcome Gemma 4: Frontier multimodal intelligence on device

## When to Use
- Use when working on ml fine-tuning tasks related to this source.

## Workflow
1. Review the source summary: Gemma 4 is an advanced, truly open-source multimodal LLM family (image, text, audio, video inputs) licensed under Apache 2, optimized for on-device use and long contexts up to 256K tokens. It employs innovations like Per-Layer Embeddings and a Shared KV Cache for efficiency and fine-grained token conditioning, delivering state-of-the-art performance across reasoning, coding, vision, and audio benchmarks while supporting multimodal function calling and agentic applications. Available in four sizes—including dense and mixture-of-experts architectures—Gemma 4 integrates seamlessly with popular inference engines (transformers, llama.cpp, MLX, transformers.js, mistral.rs) and supports fine-tuning on platforms like TRL and Vertex AI, enabling deployment on edge, local servers, and cloud for use cases such as interactive agents, robotics, OCR, speech-to-text, video understanding, and tool-augmented automation.
2. Apply the extracted technique to the current task.
3. Revisit the source URL for deeper implementation detail: https://huggingface.co/blog/gemma4
