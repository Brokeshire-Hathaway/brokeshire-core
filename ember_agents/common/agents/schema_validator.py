from typing import (
    ClassVar,
    Generic,
    TypeVar,
)

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator
from rich import print

from ember_agents.common.agents.entity_extractor import (
    ConfidenceLevel,
    ExtractedEntities,
    flatten_classified_entities,
)

T = TypeVar("T")


"""class ValueWithConfidence(TypedDict):
    value: str
    confidence_percentage: float"""


class InferredEntity(BaseModel, Generic[T]):
    named_entity: T
    confidence_level: ConfidenceLevel = Field(
        ...,
        description="Confidence level of the inference: low, normal, or high",
    )
    confidence_threshold: ConfidenceLevel = Field(
        default="normal", description="Minimum acceptable confidence level"
    )

    CONFIDENCE_ORDER: ClassVar[list[str]] = ["low", "normal", "high"]

    @field_validator("confidence_level")
    @classmethod
    def validate_confidence(
        cls, v: ConfidenceLevel, info: ValidationInfo
    ) -> ConfidenceLevel:
        threshold = info.data.get("confidence_threshold", "normal")
        if cls.CONFIDENCE_ORDER.index(v) < cls.CONFIDENCE_ORDER.index(threshold):
            print(f"Confidence '{v}' is below the threshold of '{threshold}'")
            print(cls)
            print(info)
            msg = f"Confidence is {v}. Unsure if '{info.data["named_entity"]}' is the correct named entity."
            raise ValueError(msg)
        return v


S = TypeVar("S", bound=BaseModel)


def convert_to_schema(
    schema_class: type[S], data: ExtractedEntities, *, validate: bool = True
) -> S:
    print(f"data: {data}")
    data_model = flatten_classified_entities(data)
    print(f"data_model: {data_model}")
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
