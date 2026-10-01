from typesafe_sdk import Choice

NUMBERS = [str(n) for n in range(1, 101)]


def pick_number(jev):
    response = jev.system_one(
        "",
        {"number": Choice(instructions="Pick exactly one of the options at random.", criteria=dict.fromkeys(NUMBERS))},
    )
    return int(response.answers["number"].choice)


def repeatable_request(context, input_path=None):
    """Ask Jev to pick the secret number. Takes no input file."""

    return pick_number(context.jev)


def compare(jev, secret, guess):
    response = jev.system_one(
        {"secret_number": secret, "guess": guess},
        {
            "hint": Choice(
                instructions="Compare `guess` to `secret_number` and tell the player what to do next.",
                criteria={
                    "higher": "`guess` is less than `secret_number`",
                    "lower": "`guess` is greater than `secret_number`",
                    "match": "`guess` equals `secret_number`",
                },
            )
        },
    )
    return response.answers["hint"]


def read_guess():
    while True:
        text = input("Your guess (1-100): ").strip()
        if text.isdigit() and 1 <= int(text) <= 100:
            return int(text)
        print("Enter a whole number from 1 to 100.")


def start_workflow(context):
    jev = context.jev
    secret = pick_number(jev)
    print("\nJev has picked a number between 1 and 100.\n")

    while True:
        hint = compare(jev, secret, read_guess())

        if hint.choice == "match":
            print(f"You guessed it! The number was {secret}.")
            return

        print(f"  Jev says: {hint.choice}  (confidence {hint.confidence:.2f})")
