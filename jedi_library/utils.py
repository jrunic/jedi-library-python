import re


def prepare_prompt(template: str, variables: dict | None = None) -> str:
    if not variables:
        remaining = re.findall(r"\{\$\w+\}", template)
        if remaining:
            raise ValueError(f"Placeholders não substituídos: {remaining}")
        return template

    result = template
    for key, value in variables.items():
        placeholder = "{$" + key + "}"
        if placeholder not in result:
            raise ValueError(
                f"Placeholder '{{${key}}}' (chave '{key}') não encontrado no template."
            )
        result = result.replace(placeholder, str(value))

    remaining = re.findall(r"\{\$\w+\}", result)
    if remaining:
        raise ValueError(f"Placeholders não substituídos no template: {remaining}")

    return result
