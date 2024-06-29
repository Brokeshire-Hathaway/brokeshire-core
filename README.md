# Ember Agents

The Ember AI agent swarm for intent based cognition and reasoning.

## Setup
This project is meant to be built using `pdm`, a modern `python` project manager to
handle dependencies, scripts and unify the development workflow between all developers
involved. To install the dependencies and create the first virtual environment run
in your terminal at the root of this repository:

```bash
pdm install
```

After that, a `.venv` folder with the virtual environment with the correct dependencies
will be created.

To run your API, you need to setup three API keys:
- [Open AI](https://openai.com/): An open AI key. For the education step to work, you'll need a Tier 1 account, for which you will need a minimum 5 dollar charge in the account.
- [Cohere](https://cohere.com/): A Cohere key, you can also get a free one by creating an account.
- [Pinecone](https://app.pinecone.io/): A Pinecone key, you can also get a free one by creating an account. Additionally, through the `pinecone` app, create an index call `ember`. When configuring the model select dimensions as `1024` and metric as `cosine`.

Create the `.env`:

```
COHERE_API_KEY=your_cohere_api_key
OPENAI_API_KEY="your_openai_api_key"
PINECONE_API_KEY="your_pinecone_key"
TRANSACTION_SERVICE_URL="http://localhost:3000"
FIREWORKS_API_KEY="your_fireworks_api_key"
```

After that, start the project by running:

```bash
pdm run dev
```

You should see something similar to if it was run successfully:

```
Initializing ember_agents package...
...ember_agents package initialized
COHERE_API_KEY
<YOUR_COHERE_API_KEY_HERE>
2024-03-28 17:03:24 INFO semantic_router.utils.logger Initializing RouteLayer
INFO:     Started server process [36108]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8101 (Press CTRL+C to quit)
```
