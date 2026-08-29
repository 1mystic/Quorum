from app.utils.hashing import hash_password, verify_password, password_fingerprint


def test_hash_password_is_not_plain_text():
    """Ensure that the hashed password does not match the original plain text"""
    hashed = hash_password("MyPassword123")
    assert hashed != "MyPassword123"
    assert isinstance(hashed, str)


def test_verify_password_success():
    """Ensure that a correct password successfully verifies against its hash"""
    hashed = hash_password("MyPassword123")
    assert verify_password("MyPassword123", hashed) is True


def test_verify_password_failure():
    """Ensure that an incorrect password fails to verify against the hash"""
    hashed = hash_password("MyPassword123")
    assert verify_password("WrongPassword", hashed) is False


def test_password_fingerprint_is_deterministic():
    """Ensure calling fingerprint on the same hash returns the exact same string"""
    hashed = hash_password("MyPassword123")
    assert password_fingerprint(hashed) == password_fingerprint(hashed)


def test_password_fingerprint_changes_for_different_passwords():
    """Ensure two different password hashes produce different fingerprints"""
    hash1 = hash_password("PasswordOne@123")
    hash2 = hash_password("PasswordTwo@456")
    assert password_fingerprint(hash1) != password_fingerprint(hash2)


def test_password_fingerprint_length():
    """Ensure the fingerprint is exactly 16 characters long"""
    hashed = hash_password("MyPassword123")
    fp = password_fingerprint(hashed)
    assert len(fp) == 16
    assert isinstance(fp, str)
