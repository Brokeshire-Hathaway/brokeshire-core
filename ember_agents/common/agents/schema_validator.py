from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from ember_agents.common.agents.entity_extractor import ExtractedEntities

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
    def validate_confidence(cls, v, info):
        threshold = info.data.get("confidence_threshold", 0.8)
        if v < threshold:
            msg = f"Confidence {v} is below the threshold of {threshold}"
            raise ValueError(msg)
        return v


S = TypeVar("S", bound=BaseModel)


def convert_to_schema(
    schema_class: type[S], data: ExtractedEntities, *, validate: bool = True
) -> S:
    data_model = {
        classified_entity["category"]["value"]: classified_entity["named_entity"]
        for _, classified_entity in enumerate(data["classified_entities"])
    }
    if validate:
        return schema_class.model_validate(data_model)
    else:
        return schema_class.model_construct(None, **data_model)
