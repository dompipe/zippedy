#!/usr/bin/env python3
"""
Keystone-based file compression/decompression.

Compression processes 2 bits at a time, storing ONLY the 'right' fraction.
No other data - just the fractions needed to recover the bits.
"""

from keystone import keystone_pair_exact
from fractions import Fraction
import tempfile
import os


def bits_to_2bit_values(data: bytes) -> list[int]:
    """
    Extract 2-bit values from data.
    Each 2 bits becomes a value 0-3.
    """
    values = []
    for byte in data:
        for shift in [6, 4, 2, 0]:
            two_bit_value = (byte >> shift) & 0b11
            values.append(two_bit_value)
    return values


def two_bit_values_to_bytes(values: list[int]) -> bytes:
    """Reconstruct bytes from 2-bit values."""
    result = bytearray()
    for i in range(0, len(values), 4):
        byte = 0
        for j in range(min(4, len(values) - i)):
            byte |= (values[i + j] & 0b11) << (6 - j * 2)
        result.append(byte)
    return bytes(result)


def compress_file(input_file, output_file):
    """
    Compress: Extract 2-bit values, generate keystone pairs, store ONLY 'right' fractions.
    """
    with open(input_file, "rb") as f:
        data = f.read()
    
    original_size = len(data)
    two_bit_values = bits_to_2bit_values(data)
    
    print(f"Compressing {original_size} bytes → {len(two_bit_values)} 2-bit values")
    print(f"Generating keystone pairs (n=4)...\n")
    
    # Show first 20 values and their right fractions
    print(f"{'Index':<6} | {'v':<3} | {'right fraction':<30} | {'decimal':<15}")
    print("-" * 75)
    
    right_fractions = []
    n = 4
    
    for idx, v in enumerate(two_bit_values):
        _, right = keystone_pair_exact(v, n)
        right_fractions.append(right)
        
        if idx < 20:
            print(f"{idx:<6} | {v:<3} | {str(right):<30} | {float(right):<15.10f}")
    
    if len(two_bit_values) > 20:
        print(f"... ({len(two_bit_values) - 20} more)")
    
    # Write ONLY the right fractions to file
    with open(output_file, "wb") as f:
        # Metadata: original size and count
        f.write(original_size.to_bytes(4, "big"))
        f.write(len(right_fractions).to_bytes(4, "big"))
        
        # Each right fraction: numerator_length, numerator, denominator_length, denominator
        for right in right_fractions:
            num_bytes = right.numerator.to_bytes((right.numerator.bit_length() + 7) // 8 or 1, "big")
            den_bytes = right.denominator.to_bytes((right.denominator.bit_length() + 7) // 8 or 1, "big")
            
            f.write(len(num_bytes).to_bytes(1, "big"))
            f.write(num_bytes)
            f.write(len(den_bytes).to_bytes(1, "big"))
            f.write(den_bytes)
    
    comp_size = os.path.getsize(output_file)
    print(f"\n✓ Compression complete")
    print(f"  Original: {original_size} bytes")
    print(f"  Compressed: {comp_size} bytes")
    print(f"  Ratio: {comp_size / original_size:.2%}")
    
    return original_size, comp_size, len(right_fractions)


def decompress_file(input_file, output_file):
    """
    Decompress: Read right fractions, recover v values (0-3), reconstruct bytes.
    """
    with open(input_file, "rb") as f:
        original_size = int.from_bytes(f.read(4), "big")
        total_fractions = int.from_bytes(f.read(4), "big")
        
        recovered_values = []
        n = 4
        
        print(f"Decompressing {total_fractions} right fractions...\n")
        
        for idx in range(total_fractions):
            # Read fraction
            num_len = int.from_bytes(f.read(1), "big")
            num = int.from_bytes(f.read(num_len), "big")
            den_len = int.from_bytes(f.read(1), "big")
            den = int.from_bytes(f.read(den_len), "big")
            
            right = Fraction(num, den)
            
            # Recover v by testing 0-3
            found = False
            for v in range(4):
                _, expected_right = keystone_pair_exact(v, n)
                if expected_right == right:
                    recovered_values.append(v)
                    if idx < 20:
                        print(f"  Fraction {idx}: {str(right):<30} → v={v}")
                    found = True
                    break
            
            if not found:
                raise ValueError(f"Could not recover bit value {idx} from {right}")
        
        if total_fractions > 20:
            print(f"  ... ({total_fractions - 20} more)")
    
    # Reconstruct bytes
    recovered_data = two_bit_values_to_bytes(recovered_values)[:original_size]
    
    with open(output_file, "wb") as f:
        f.write(recovered_data)
    
    print(f"\n✓ Decompression complete: {len(recovered_data)} bytes recovered")
    
    return recovered_data


def test_compression():
    """Test compression and decompression."""
    
    print("=" * 80)
    print("KEYSTONE COMPRESSION - STORING ONLY 'RIGHT' FRACTIONS")
    print("=" * 80)
    print()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        original_file = os.path.join(tmpdir, "original.txt")
        compressed_file = os.path.join(tmpdir, "compressed.bin")
        decompressed_file = os.path.join(tmpdir, "decompressed.txt")
        
        test_data = b"Hello, World! This is a keystone compression test. " * 3
        
        print(f"Original: {test_data[:50]}...")
        print(f"Size: {len(test_data)} bytes\n")
        
        with open(original_file, "wb") as f:
            f.write(test_data)
        
        print("COMPRESSION:")
        print("-" * 80)
        orig_size, comp_size, num_fractions = compress_file(original_file, compressed_file)
        
        print("\n" + "=" * 80)
        print("DECOMPRESSION:")
        print("-" * 80)
        recovered = decompress_file(compressed_file, decompressed_file)
        
        print("\n" + "=" * 80)
        print("VERIFICATION:")
        print("-" * 80)
        
        with open(decompressed_file, "rb") as f:
            recovered_data = f.read()
        
        if recovered_data == test_data:
            print("✓ PERFECT MATCH!")
        else:
            print("✗ MISMATCH")
        
        print("\n" + "=" * 80)
        print(f"Original:    {orig_size} bytes")
        print(f"Compressed:  {comp_size} bytes")
        print(f"Ratio:       {comp_size / orig_size:.2%}")
        print(f"Data stored: {num_fractions} 'right' fractions only")
        print("=" * 80)


if __name__ == "__main__":
    test_compression()
