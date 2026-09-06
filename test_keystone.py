#!/usr/bin/env python3
"""Test keystone encoding/decoding with file I/O."""

from keystone import (
    keystone_pair_exact,
    encode_keystone,
    decode_keystone,
    batch_save_keystones,
    batch_load_and_verify,
    keystone_record,
)
import os
import tempfile


def main():
    # Create 8 test cases
    test_cases = [
        (1, 1),
        (13, 7),
        (42, 5),
        (255, 16),
        (512, 20),
        (1000, 31),
        (5555, 100),
        (65535, 256),
    ]

    print("=" * 70)
    print("KEYSTONE ENCODING/DECODING TEST")
    print("=" * 70)

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\nUsing temporary directory: {tmpdir}\n")

        # Save all keystones
        print("SAVING KEYSTONES...")
        print("-" * 70)
        batch_save_keystones(test_cases, tmpdir)

        for v, n in test_cases:
            record = keystone_record(v, n)
            binary_file = os.path.join(tmpdir, f"keystone_v{v}_n{n}.bin")
            file_size = os.path.getsize(binary_file)
            print(
                f"  v={v:5d}, n={n:3d} → left={record['left_num']:8d}/{record['left_den']:3d}, "
                f"right={record['right_num']:8d}/{record['right_den']:3d} "
                f"(binary: {file_size} bytes)"
            )

        print("\n" + "=" * 70)
        print("LOADING AND VERIFYING KEYSTONES...")
        print("-" * 70)

        # Verify round-trip
        all_passed = True
        for v, n in test_cases:
            original = keystone_pair_exact(v, n)
            binary_file = os.path.join(tmpdir, f"keystone_v{v}_n{n}.bin")

            with open(binary_file, "rb") as f:
                data = f.read()

            restored = decode_keystone(data)

            match = original == restored
            status = "✓ PASS" if match else "✗ FAIL"
            all_passed = all_passed and match

            print(
                f"{status} | v={v:5d}, n={n:3d} | "
                f"original: ({original[0]}, {original[1]}) | "
                f"restored: ({restored[0]}, {restored[1]})"
            )

        print("\n" + "=" * 70)
        if all_passed:
            print("ALL TESTS PASSED ✓")
        else:
            print("SOME TESTS FAILED ✗")
        print("=" * 70)


if __name__ == "__main__":
    main()
