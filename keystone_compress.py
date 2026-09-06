#!/usr/bin/env python3
"""
Keystone-based file compression/decompression.

Compression processes 2 bits at a time, storing BOTH 'left' and 'right' fractions.
Both sides needed to uniquely recover the original bits.
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
    Compress: Extract 2-bit values, generate keystone pairs, store BOTH 'left' and 'right' fractions.
    """
    with open(input_file, "rb") as f:
        data = f.read()
    
    original_size = len(data)
    two_bit_values = bits_to_2bit_values(data)
    
    print(f"Compressing {original_size} bytes → {len(two_bit_values)} 2-bit values")
    print(f"Generating keystone pairs (n=4)...\n")
    
    # Show first 20 values and their left/right fractions
    print(f"{'Index':<6} | {'v':<3} | {'left':<20} | {'right':<20}")
    print("-" * 85)
    
    keystone_pairs = []
    n = 4
    
    for idx, v in enumerate(two_bit_values):
        left, right = keystone_pair_exact(v, n)
        keystone_pairs.append((left, right))
        
        if idx < 20:
            print(f"{idx:<6} | {v:<3} | {str(left):<20} | {str(right):<20}")
    
    if len(two_bit_values) > 20:
        print(f"... ({len(two_bit_values) - 20} more)")
    
    # Write both left and right fractions to file
    with open(output_file, "wb") as f:
        # Metadata: original size and count
        f.write(original_size.to_bytes(4, "big"))
        f.write(len(keystone_pairs).to_bytes(4, "big"))
        
        # Each pair: left numerator, left denominator, right numerator, right denominator
        for left, right in keystone_pairs:
            # Left fraction
            left_num_bytes = left.numerator.to_bytes((left.numerator.bit_length() + 7) // 8 or 1, "big")
            left_den_bytes = left.denominator.to_bytes((left.denominator.bit_length() + 7) // 8 or 1, "big")
            
            # Right fraction
            right_num_bytes = right.numerator.to_bytes((right.numerator.bit_length() + 7) // 8 or 1, "big")
            right_den_bytes = right.denominator.to_bytes((right.denominator.bit_length() + 7) // 8 or 1, "big")
            
            # Write left
            f.write(len(left_num_bytes).to_bytes(1, "big"))
            f.write(left_num_bytes)
            f.write(len(left_den_bytes).to_bytes(1, "big"))
            f.write(left_den_bytes)
            
            # Write right
            f.write(len(right_num_bytes).to_bytes(1, "big"))
            f.write(right_num_bytes)
            f.write(len(right_den_bytes).to_bytes(1, "big"))
            f.write(right_den_bytes)
    
    comp_size = os.path.getsize(output_file)
    print(f"\n✓ Compression complete")
    print(f"  Original: {original_size} bytes")
    print(f"  Compressed: {comp_size} bytes")
    print(f"  Ratio: {comp_size / original_size:.2%}")
    
    return original_size, comp_size, len(keystone_pairs)


def decompress_file(input_file, output_file):
    """
    Decompress: Read left and right fractions, recover v values (0-3), reconstruct bytes.
    """
    with open(input_file, "rb") as f:
        original_size = int.from_bytes(f.read(4), "big")
        total_pairs = int.from_bytes(f.read(4), "big")
        
        recovered_values = []
        n = 4
        
        print(f"Decompressing {total_pairs} keystone pairs...\n")
        print(f"{'Index':<6} | {'left':<20} | {'right':<20} | {'recovered v':<6}")
        print("-" * 85)
        
        for idx in range(total_pairs):
            # Read left fraction
            left_num_len = int.from_bytes(f.read(1), "big")
            left_num = int.from_bytes(f.read(left_num_len), "big")
            left_den_len = int.from_bytes(f.read(1), "big")
            left_den = int.from_bytes(f.read(left_den_len), "big")
            
            # Read right fraction
            right_num_len = int.from_bytes(f.read(1), "big")
            right_num = int.from_bytes(f.read(right_num_len), "big")
            right_den_len = int.from_bytes(f.read(1), "big")
            right_den = int.from_bytes(f.read(right_den_len), "big")
            
            left = Fraction(left_num, left_den)
            right = Fraction(right_num, right_den)
            
            # Recover v by testing 0-3 against BOTH fractions
            found = False
            for v in range(4):
                expected_left, expected_right = keystone_pair_exact(v, n)
                
                # Both must match
                if expected_left == left and expected_right == right:
                    recovered_values.append(v)
                    if idx < 20:
                        print(f"{idx:<6} | {str(left):<20} | {str(right):<20} | {v:<6}")
                    found = True
                    break
            
            if not found:
                raise ValueError(f"Could not recover v from pair {idx}: left={left}, right={right}")
        
        if total_pairs > 20:
            print(f"... ({total_pairs - 20} more)")
    
    # Reconstruct bytes
    recovered_data = two_bit_values_to_bytes(recovered_values)[:original_size]
    
    with open(output_file, "wb") as f:
        f.write(recovered_data)
    
    print(f"\n✓ Decompression complete: {len(recovered_data)} bytes recovered")
    
    return recovered_data


def test_compression():
    """Test compression and decompression."""
    
    print("=" * 85)
    print("KEYSTONE COMPRESSION - STORING BOTH 'LEFT' AND 'RIGHT' FRACTIONS")
    print("=" * 85)
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
        print("-" * 85)
        orig_size, comp_size, num_pairs = compress_file(original_file, compressed_file)
        
        print("\n" + "=" * 85)
        print("DECOMPRESSION:")
        print("-" * 85)
        recovered = decompress_file(compressed_file, decompressed_file)
        
        print("\n" + "=" * 85)
        print("VERIFICATION:")
        print("-" * 85)
        
        with open(decompressed_file, "rb") as f:
            recovered_data = f.read()
        
        if recovered_data == test_data:
            print("✓ PERFECT MATCH!")
        else:
            print("✗ MISMATCH")
        
        print("\n" + "=" * 85)
        print(f"Original:    {orig_size} bytes")
        print(f"Compressed:  {comp_size} bytes")
        print(f"Ratio:       {comp_size / orig_size:.2%}")
        print(f"Data stored: {num_pairs} keystone pairs (both left + right fractions)")
        print("=" * 85)


if __name__ == "__main__":
    test_compression()
