import re

from defusedxml import ElementTree
from rich.console import Console

console = Console()


def parse_response(response: str, thinking_tag: str, response_tag: str):
    # Extract thinking content before removing it
    thinking_match = re.search(
        fr"<{thinking_tag}>(.*?)</{thinking_tag}>", response, re.DOTALL
    )
    thinking_content = None
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
    else:
        # If no tags found, remove any remaining tags and normalize whitespace
        sanitized = re.sub(r"</?[^>]+>\s*", "", response).strip()
        console.print(f"[green]Sanitized response: {sanitized}[/green]")

    return (sanitized, thinking_content) if thinking_content else (sanitized,)


def extract_xml_content(xml_string: str, tag_name: str) -> str | None:
    # Wrap the input in a root element
    wrapped_xml = f"<root>{xml_string}</root>"
    root = ElementTree.fromstring(wrapped_xml)
    element = root.find(f".//{tag_name}")
    return (
        element.text.strip()
        if element is not None and element.text is not None
        else None
    )
