from pydantic import BaseModel


def iterate_fields(model: BaseModel):
    for key in model.model_dump(exclude_unset=True):
        value = getattr(model, key)
        field_info = model.model_fields[key]
        name = key if field_info.alias is None else field_info.alias
        yield name, value
