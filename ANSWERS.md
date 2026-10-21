# Engineering Knowledge Answers

## 1. Describe differences between REST API, MCP in the context of AI.

REST API is a way for applications to communicate using HTTP requests (GET, POST, PUT, DELETE) to send and receive data. In AI, it's commonly used to connect an app to an AI model or other services.

MCP (Model Context Protocol) is designed specifically for AI, allowing models to connect with external tools, databases, and services through a standard protocol.

The main difference is that REST API is for general communication between applications, while MCP makes it easier for AI models to discover and use tools without needing a separate custom integration for each one.

## 2. How REST API, MCP, can improve the AI use case?

REST API and MCP can make AI more useful by allowing it to connect with external data and services instead of only relying on its training data.

REST API helps AI get real-time information, send data, and interact with other applications. MCP makes it easier for AI to access different tools and data sources through one standard protocol.

They help AI do more than just answer questions. For example, AI can retrieve data from a database, analyse it, and even perform actions like creating reports or updating records automatically.

## 3. How do you ensure that your AI agent answers correctly?

To make sure an AI agent gives accurate answers, we need to provide clear instructions, use reliable and up to date data sources, and apply RAG (retrieval augmented generation) so that the AI can retrieve relevant information instead of just relying on its training data.

I would also test the agent with different scenarios, validate its responses, and monitor its performance regularly. If the AI is unsure about something, it should be able to say so instead of making up an answer.

## 4. Describe what can you do with Docker / Containerize environment in the context of AI.

Docker can be used to package AI applications along with all their dependencies, libraries, and configurations into a container, so they can run consistently across different environments.

In AI projects, I can use Docker to deploy AI models, run APIs, set up databases or vector databases, and manage services like LLMs and AI agents. Docker Compose also helps run multiple services together.

It makes development, testing, and deployment easier because I don't need to worry too much about environment differences or dependency issues.

## 5. Fine-tuning an LLM from raw data

To fine tune an LLM from raw data, I would start by collecting and cleaning the data, removing duplicates, irrelevant information, and sensitive data. Then I would convert it into a structured format, like JSONL with instruction and response pairs.

After that, I would choose a pretrained model and fine tune it using methods like LoRA or QLoRA to reduce GPU and memory usage.

Once training is done, I would test the model with unseen data, evaluate the accuracy and quality of its responses, and adjust the training if needed. The goal is to make the model perform better on specific tasks or understand domain-specific knowledge.

# Coding test 

## 3. Small versus large files

A small CSV can often be parsed eagerly into a DataFrame, enabling convenient vectorized group by operations. For a multi-million-row file, avoid loading all records or creating many in-memory chunks. Stream, batch, or partition by stable key, persist intermediate results to disk, and aggregate incrementally. Splitting by byte positions risks breaking records with quoted embedded newlines; partition with a CSV-aware reader. Chunks need consistent headers, schema, and aggregation handling. The profiler itself does not split either CSV: it reads both as streams.