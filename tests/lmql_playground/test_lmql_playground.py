import os
import pytest
import lmql

@lmql.query(
    # model name is not actually used: endpoint completely overrides model selection
    "meta-llama/Llama-2-13b-chat-hf",
    # in this case, uses model from https://replicate.com/charles-dyfis-net/llama-2-13b-hf--lmtp-8bit
    endpoint="replicate:charles-dyfis-net/llama-2-13b-hf--lmtp-8bit",
    # choosing a model with the same tokenizer as meta-llama/Llama-2-13b-hf but ungated in huggingface
    tokenizer="AyyYOO/Luna-AI-Llama2-Uncensored-FP16-sharded",
)
def lmql_playground():
    '''lmql
    # Q&A prompt template
    "Q: How many cheese burgers does the average American eat in one year?"
    "The answer is:[ANSWER]."

    return ANSWER
    '''


def test_lmql_playground():
    print(f"REPLICATE_API_TOKEN: {os.getenv('REPLICATE_API_TOKEN')}")

    response = lmql_playground()
    print("=== LMQL Response ===")
    print(response)