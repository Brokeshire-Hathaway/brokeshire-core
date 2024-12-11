import re

from rich.console import Console

console = Console()


def parse_response(response: str, thinking_tag: str, response_tag: str):
    # Extract thinking content before removing it
    thinking_match = re.search(
        fr"<{thinking_tag}>(.*?)</{thinking_tag}>", response, re.DOTALL
    )
    if thinking_match:
        thinking_content = thinking_match.group(1).strip()
        console.print(f"[yellow]Thinking content: {thinking_content}[/yellow]")

    # Remove response planning sections and any following whitespace up to the next tag
    response = re.sub(
        fr"<{thinking_tag}>.*?</{thinking_tag}>\s*",
        "",
        response,
        flags=re.DOTALL,
    )

    # Then try to extract content from response tags
    response_match = re.search(
        f"<{response_tag}>(.*?)</{response_tag}>", response, re.DOTALL
    )
    if response_match:
        sanitized = response_match.group(1).strip()
        console.print(f"[green]Extracted response: {sanitized}[/green]")
        return sanitized

    # If no tags found, remove any remaining tags and normalize whitespace
    sanitized_response = re.sub(r"</?[^>]+>\s*", "", response).strip()
    console.print(f"[green]Sanitized response: {sanitized_response}[/green]")

    return sanitized_response
