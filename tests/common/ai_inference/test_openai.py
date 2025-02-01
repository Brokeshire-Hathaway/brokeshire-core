import json
from math import exp
from typing import List, Dict, Any

import pytest

from brokeshire_agents.common.ai_inference.openai import add_confidence_to_json_values

from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionTokenLogprob,
)


@pytest.mark.skip
def test_construct_logprob_json():
    logprobs = [
        ChatCompletionTokenLogprob(token="{", logprob=-0.006374875, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="\n", logprob=-0.016535155, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" ", logprob=-1.504853e-06, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" \"", logprob=-1.2664457e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="from", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="_amount", logprob=-6.2729996e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(
            token="\":", logprob=-0.00018494461, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(
            token=" [\n", logprob=-4.0961266e-05, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(
            token="   ", logprob=-0.00014442271, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(
            token=" {\n", logprob=-2.8444882e-05, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="     ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" \"", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="name", logprob=-7.89631e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="\":", logprob=-4.3202e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" \"", logprob=-4.274932e-05, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="5", logprob=-8.418666e-06, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="\"\n", logprob=-1.1041146e-05, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="   ", logprob=-7.822647e-06, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" }\n", logprob=-5.5122365e-07, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token=" ", logprob=-3.650519e-06, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" ],\n", logprob=-1.9361265e-07, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token=" ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" \"", logprob=-3.1281633e-07, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="from", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="_token", logprob=-5.5122365e-07, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="\":", logprob=-4.3202e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" [\n", logprob=-1.18755715e-05, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="   ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" {\n", logprob=-3.7697225e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="     ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" \"", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="name", logprob=-7.89631e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="\":", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" \"", logprob=-0.00015908109, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="us", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="dc", logprob=-5.5122365e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="\"\n", logprob=-1.2352386e-05, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(
            token="   ", logprob=-5.2001665e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(
            token=" }\n", logprob=-1.2664457e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token=" ", logprob=-1.3856493e-06, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" ],\n", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" \"", logprob=-1.1517961e-05, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="from", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="_network", logprob=-3.7697225e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="\":", logprob=-0.0001202317, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" [],\n", logprob=-1.9361265e-07, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token=" ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" \"", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="to", logprob=-4.3202e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="_amount", logprob=-1.2664457e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="\":", logprob=-0.012697294, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" [],\n", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" \"", logprob=-1.9361265e-07, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="to", logprob=-5.5122365e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="_token", logprob=-5.5122365e-07, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="\":", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" [\n", logprob=-1.6166903e-05, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="   ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" {\n", logprob=-0.00021521868, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="     ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" \"", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="name", logprob=-1.147242e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="\":", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" \"", logprob=-4.3202e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="eth", logprob=-6.704273e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="\"\n", logprob=-1.7239736e-05, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(
            token="   ", logprob=-2.1054253e-05, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(
            token=" }\n", logprob=-1.504853e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token=" ", logprob=-4.3202e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" ],\n", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" ", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token=" \"", logprob=0.0, top_logprobs=[]),
        ChatCompletionTokenLogprob(token="to", logprob=-3.1281633e-07, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token="_network", logprob=-8.89548e-06, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="\":", logprob=-4.00813e-06, top_logprobs=[]),
        ChatCompletionTokenLogprob(
            token=" []\n", logprob=-0.0003581072, top_logprobs=[]
        ),
        ChatCompletionTokenLogprob(token="}", logprob=-0.0003581072, top_logprobs=[]),
    ]
    expected_result = {
        "from_amount": [{"name": {"value": "5", "confidence_percentage": 99.9992}}],
        "from_token": [{"name": {"value": "usdc", "confidence_percentage": 100.0}}],
        "from_network": [],
        "to_amount": [],
        "to_token": [{"name": {"value": "eth", "confidence_percentage": 99.9999}}],
        "to_network": [],
    }

    result = add_confidence_to_json_values(logprobs)

    assert result == expected_result
