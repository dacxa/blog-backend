import unittest

from pydantic import ValidationError

from app.schemas.auth import UserCreate, UserRegister


class UserRegisterUsernameTests(unittest.TestCase):
    def make_payload(self, username: str) -> UserRegister:
        return UserRegister(
            username=username,
            email="user@example.com",
            password="secure-password",
            code="123456",
        )

    def test_accepts_chinese_username(self) -> None:
        payload = self.make_payload("路明非")

        self.assertEqual(payload.username, "路明非")

    def test_accepts_two_character_chinese_username(self) -> None:
        payload = self.make_payload("楚子")

        self.assertEqual(payload.username, "楚子")

    def test_accepts_existing_ascii_and_hyphenated_username(self) -> None:
        payload = self.make_payload("S-001_user")

        self.assertEqual(payload.username, "S-001_user")

    def test_rejects_unsafe_characters(self) -> None:
        with self.assertRaises(ValidationError):
            self.make_payload("路明非<script>")

    def test_rejects_username_outside_length_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            self.make_payload("王")

        with self.assertRaises(ValidationError):
            self.make_payload("路" * 51)

    def test_user_create_reuses_username_validation(self) -> None:
        payload = UserCreate(
            username="路明非",
            email="user@example.com",
            password="secure-password",
        )

        self.assertEqual(payload.username, "路明非")

        with self.assertRaises(ValidationError):
            UserCreate(
                username="路 明非",
                email="user@example.com",
                password="secure-password",
            )


if __name__ == "__main__":
    unittest.main()
