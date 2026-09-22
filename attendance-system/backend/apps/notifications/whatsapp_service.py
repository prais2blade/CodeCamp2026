import urllib.parse


def build_whatsapp_url(

    phone_number,

    message

):

    phone_number = str(
        phone_number
    )

    phone_number = (
        phone_number
        .replace("+", "")
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if phone_number.startswith("0"):

        phone_number = (
            "234" +
            phone_number[1:]
        )

    encoded_message = urllib.parse.quote(
        message
    )

    return (

        f"https://wa.me/"
        f"{phone_number}"
        f"?text={encoded_message}"

    )