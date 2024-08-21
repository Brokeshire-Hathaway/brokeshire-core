from typing import Any, Generic, Type, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, Field, ValidationInfo, field_validator
from rich import print

from ember_agents.common.agents.entity_extractor import (
    ExtractedEntities,
    ValueWithConfidence,
)

T = TypeVar("T")


class InferredValue(BaseModel, Generic[T]):
    value: T
    confidence_percentage: float = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence level of the inference, between 0 and 100 percent",
    )
    confidence_threshold: float = Field(
        default=80, ge=0, le=100, description="Minimum acceptable confidence level"
    )

    @field_validator("confidence_percentage")
    @classmethod
    def validate_confidence(cls, v: float, info: ValidationInfo) -> float:
        threshold = info.data.get("confidence_threshold", 80)
        if v < threshold:
            print(f"Confidence {v} is below the threshold of {threshold}")
            msg = "Unsure if this is the correct value"
            raise ValueError(msg)
        return v


S = TypeVar("S", bound=BaseModel)


def flatten_classified_entities(
    data: ExtractedEntities,
) -> dict[str, ValueWithConfidence]:
    return {
        classified_entity["category"]["value"]: {
            "value": classified_entity["named_entity"]["value"],
            "confidence_percentage": min(
                classified_entity["category"]["confidence_percentage"],
                classified_entity["named_entity"]["confidence_percentage"],
            ),
        }
        for classified_entity in data["classified_entities"]
    }


def convert_to_schema(
    schema_class: type[S], data: ExtractedEntities, *, validate: bool = True
) -> S:
    print(data)
    data_model = flatten_classified_entities(data)
    print(data_model)
    """if validate:
        model = schema_class.model_validate(data_model)
        print(model)
        return model
    else:
        model = schema_class.model_construct(None, **data_model)
        print(model)
        return model"""
    model = schema_class.model_validate(data_model)
    return model
