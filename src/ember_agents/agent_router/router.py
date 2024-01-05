def router(intent: str) -> str:
    """Route an intent to the appropriate agent."""
    if intent == "What is DeFi?":
        return "default"
    elif intent.startswith("Send"):
        return "send"
    elif intent.startswith("What is the price of"):
        return "market"
    else:
        return "default"
