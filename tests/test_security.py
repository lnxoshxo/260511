from zipora.core.security import generate_password, password_strength


def test_password_strength_labels_strong_password() -> None:
    score, label = password_strength("A-very-strong-password-123")

    assert score >= 4
    assert label in {"强", "很强"}


def test_generate_password_minimum_length() -> None:
    password = generate_password(8)

    assert len(password) >= 12
