from __future__ import annotations

from fractions import Fraction
from typing import Iterable
import json
import os


def keystone_pair_exact(v: int, n: int) -> tuple[Fraction, Fraction]:
    """
    Return the exact keystone pair for integer v and positive integer n.

    The binary representation of v is read as decimal digits.

    Example:
        v = 13
        binary(v) = "1101"
        b = 1101

        left  = v/n + b
        right = b/n + v
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if v < 0:
        raise ValueError("v must be non-negative")

    b = int(f"{v:b}")
    left = Fraction(v, n) + b
    right = Fraction(b, n) + v
    return left, right


def fraction_to_ints(f: Fraction) -> tuple[int, int]:
    """Return a Fraction as (numerator, denominator)."""
    return f.numerator, f.denominator


def ints_to_fraction(numerator: int, denominator: int) -> Fraction:
    """Rebuild a Fraction from integer numerator and denominator."""
    if denominator == 0:
        raise ValueError("denominator cannot be zero")
    return Fraction(numerator, denominator)


def _uint_to_min_bytes(x: int) -> bytes:
    """
    Encode one non-negative integer in the fewest possible big-endian bytes.
    
    Returns minimal representation without leading zeros.
    Special case: 0 returns b"" (empty), length prefix handles it.
    """
    if x < 0:
        raise ValueError("dense integer encoding only supports non-negative integers")
    if x == 0:
        return b""
    return x.to_bytes((x.bit_length() + 7) // 8, "big")


def ints_to_dense(nums: Iterable[int]) -> bytes:
    """
    Pack non-negative integers into a compact byte stream.

    Format for each integer:
        [byte-length encoded as 4-byte unsigned big-endian]
        [integer bytes, minimal big-endian representation without leading zeros]

    This is exact and reversible.
    """
    out = bytearray()

    for x in nums:
        raw = _uint_to_min_bytes(int(x))
        if len(raw) > 0xFFFFFFFF:
            raise OverflowError("integer byte representation is too large")
        out.extend(len(raw).to_bytes(4, "big"))
        out.extend(raw)

    return bytes(out)


def dense_to_ints(data: bytes) -> list[int]:
    """Reverse ints_to_dense()."""
    nums: list[int] = []
    pos = 0
    size = len(data)

    while pos < size:
        if pos + 4 > size:
            raise ValueError("truncated dense integer length prefix")

        length = int.from_bytes(data[pos:pos + 4], "big")
        pos += 4

        if length < 0:
            raise ValueError("invalid dense integer byte length")

        if length == 0:
            # Zero is encoded as length 0 with no payload
            nums.append(0)
        else:
            end = pos + length
            if end > size:
                raise ValueError("truncated dense integer payload")

            nums.append(int.from_bytes(data[pos:end], "big"))
            pos = end

    return nums


def fractions_to_dense(values: Iterable[Fraction]) -> bytes:
    """
    Encode Fractions exactly.

    Each fraction contributes:
        numerator, denominator

    This implementation expects non-negative numerators.
    Keystone pairs produced from non-negative v satisfy that requirement.
    """
    ints: list[int] = []

    for f in values:
        if f.numerator < 0:
            raise ValueError("negative fractions are not supported by this dense format")
        ints.extend((f.numerator, f.denominator))

    return ints_to_dense(ints)


def dense_to_fractions(data: bytes) -> list[Fraction]:
    """Reverse fractions_to_dense()."""
    ints = dense_to_ints(data)

    if len(ints) % 2:
        raise ValueError("fraction stream contains an odd number of integers")

    out: list[Fraction] = []
    for i in range(0, len(ints), 2):
        numerator = ints[i]
        denominator = ints[i + 1]
        if denominator == 0:
            raise ValueError("fraction denominator cannot be zero")
        out.append(Fraction(numerator, denominator))

    return out


def encode_keystone(v: int, n: int) -> bytes:
    """Compute one exact keystone pair and encode it losslessly."""
    left, right = keystone_pair_exact(v, n)
    return fractions_to_dense((left, right))


def decode_keystone(data: bytes) -> tuple[Fraction, Fraction]:
    """Decode bytes produced by encode_keystone()."""
    values = dense_to_fractions(data)

    if len(values) != 2:
        raise ValueError("encoded keystone data must contain exactly two fractions")

    return values[0], values[1]


def keystone_record(v: int, n: int) -> dict[str, object]:
    """Return a readable record containing all core keystone values."""
    left, right = keystone_pair_exact(v, n)
    binary_text = f"{v:b}"
    binary_as_decimal = int(binary_text)

    return {
        "v": v,
        "n": n,
        "binary": binary_text,
        "binary_as_decimal": binary_as_decimal,
        "left": str(left),
        "right": str(right),
        "left_num": left.numerator,
        "left_den": left.denominator,
        "right_num": right.numerator,
        "right_den": right.denominator,
    }


def save_keystone_record(v: int, n: int, filename: str) -> None:
    """Save a keystone record to a JSON file."""
    record = keystone_record(v, n)
    with open(filename, "w") as f:
        json.dump(record, f, indent=2)


def load_keystone_record(filename: str) -> dict[str, object]:
    """Load a keystone record from a JSON file."""
    with open(filename, "r") as f:
        return json.load(f)


def save_encoded_keystone(v: int, n: int, filename: str) -> None:
    """Save encoded keystone data to a binary file."""
    packed = encode_keystone(v, n)
    with open(filename, "wb") as f:
        f.write(packed)


def load_encoded_keystone(filename: str) -> tuple[Fraction, Fraction]:
    """Load and decode keystone data from a binary file."""
    with open(filename, "rb") as f:
        data = f.read()
    return decode_keystone(data)


def batch_save_keystones(test_cases: list[tuple[int, int]], output_dir: str) -> None:
    """Save multiple keystone records and their encoded forms to a directory."""
    os.makedirs(output_dir, exist_ok=True)

    for v, n in test_cases:
        # Save JSON record
        record_file = os.path.join(output_dir, f"keystone_v{v}_n{n}.json")
        save_keystone_record(v, n, record_file)

        # Save binary encoded data
        binary_file = os.path.join(output_dir, f"keystone_v{v}_n{n}.bin")
        save_encoded_keystone(v, n, binary_file)


def batch_load_and_verify(output_dir: str) -> dict[str, bool]:
    """Load and verify all keystone files in a directory."""
    results = {}

    for filename in sorted(os.listdir(output_dir)):
        if filename.endswith(".bin"):
            filepath = os.path.join(output_dir, filename)
            try:
                left, right = load_encoded_keystone(filepath)
                results[filename] = True
                print(f"✓ {filename}: left={left}, right={right}")
            except Exception as e:
                results[filename] = False
                print(f"✗ {filename}: {e}")

    return results


def self_check() -> None:
    """Run a few exact round-trip checks."""
    tests = [
        (1, 1),
        (2, 3),
        (5, 7),
        (13, 9),
        (255, 16),
        (1024, 31),
    ]

    for v, n in tests:
        original = keystone_pair_exact(v, n)
        packed = encode_keystone(v, n)
        restored = decode_keystone(packed)
        assert restored == original, (v, n, original, restored)


if __name__ == "__main__":
    self_check()

    v = 13
    n = 7

    record = keystone_record(v, n)
    packed = encode_keystone(v, n)
    restored = decode_keystone(packed)

    print("Keystone exact demo")
    print("-------------------")
    print(f"v                  = {record['v']}")
    print(f"n                  = {record['n']}")
    print(f"binary(v)          = {record['binary']}")
    print(f"binary as decimal  = {record['binary_as_decimal']}")
    print(f"left               = {record['left']}")
    print(f"right              = {record['right']}")
    print(f"packed bytes       = {packed.hex()}")
    print(f"packed byte length = {len(packed)}")
    print(f"decoded left       = {restored[0]}")
    print(f"decoded right      = {restored[1]}")
    print("self-check          = OK")
