import phonenumbers


def normalizar(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        numero = phonenumbers.parse(raw, "BR")
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(numero):
        return None
    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)
