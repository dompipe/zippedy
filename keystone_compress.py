#!/usr/bin/env python3
"""
Keystone-based file compression/decompression.

Compression processes 2 bits at a time, creating a keystone pair for each 2-bit value.
Stores actual fraction values to examine the mathematics.
"""

from keystone import keystone_pair_exact
from fractions import Fraction
import tempfile
import os
import json


def bits_to_2bit_values(data: bytes) -> list[int]:
    """
    Extract 2-bit values from data.
    
    Each 2 bits becomes a value 0-3.
    Processes from MSB to LSB within each byte.
    """
    values = []
    
    for byte in data:
        # Extract 2 bits at a time from MSB to LSB
        for shift in [6, 4, 2, 0]:
            two_bit_value = (byte >> shift) & 0b11
            values.append(two_bit_value)
    
    return values


def two_bit_values_to_bytes(values: list[int]) -> bytes:
    """
    Reconstruct bytes from 2-bit values.
    
    Each 4 values create one byte.
    """
    result = bytearray()
    
    # Process 4 values at a time
    for i in range(0, len(values), 4):
        byte = 0
        for j in range(min(4, len(values) - i)):
            byte |= (values[i + j] & 0b11) << (6 - j * 2)
        result.append(byte)
    
    return bytes(result)


def compress_file(input_file, output_file):
    """
    Compress a file by processing 2 bits at a time.
    
    For each 2-bit value (0-3):
        - Use v = 0, 1, 2, or 3 (the 2-bit value)
        - Use n = 4 (fixed denominator)
        - Store the actual (left, right) fraction pairs
    """
    with open(input_file, "rb") as f:
        data = f.read()
    
    original_size = len(data)
    total_bits = original_size * 8
    total_2bit_values = (total_bits + 1) // 2  # Round up
    
    print(f"Compressing {original_size} bytes ({total_bits} bits)...")
    print(f"Processing 2 bits at a time → {total_2bit_values} keystone pairs\n")
    
    # Extract 2-bit values
    two_bit_values = bits_to_2bit_values(data)
    
    keystone_data = []
    n = 4  # Fixed denominator for 2-bit values (0-3)
    
    # Generate keystone pair for each 2-bit value
    print(f"{'Index':<6} | {'v':<3} | {'binary':<4} | {'left':<20} | {'right':<20}")
    print("-" * 80)
    
    for idx, v in enumerate(two_bit_values[:20]):  # Show first 20
        left, right = keystone_pair_exact(v, n)
        keystone_data.append({
            "v": v,
            "n": n,
            "binary": f"{v:b}",
            "left_numerator": left.numerator,
            "left_denominator": left.denominator,
            "left_decimal": float(left),
            "right_numerator": right.numerator,
            "right_denominator": right.denominator,
            "right_decimal": float(right),
        })
        
        print(f"{idx:<6} | {v:<3} | {f'{v:b}':<4} | {str(left):<20} | {str(right):<20}")
    
    if len(two_bit_values) > 20:
        print(f"... ({len(two_bit_values) - 20} more pairs)")
    
    # Write all keystone data to JSON for examination
    output_json = output_file.replace('.bin', '.json')
    with open(output_json, "w") as f:
        json.dump({
            "original_size": original_size,
            "total_2bit_values": total_2bit_values,
            "n": n,
            "keystone_pairs": keystone_data[:50]  # Store first 50 for inspection
        }, f, indent=2)
    
    print(f"\n✓ Keystone data saved to {output_json}")
    
    # Store the fractions in a compact binary format
    with open(output_file, "wb") as f:
        # Write metadata
        f.write(original_size.to_bytes(4, "big"))
        f.write(total_2bit_values.to_bytes(4, "big"))
        
        # Write all keystone pairs (each pair: v, left_num, left_den, right_num, right_den)
        for idx, v in enumerate(two_bit_values):
            left, right = keystone_pair_exact(v, n)
            
            # Encode each value compactly
            v_bytes = v.to_bytes(1, "big")
            left_num_bytes = left.numerator.to_bytes((left.numerator.bit_length() + 7) // 8 or 1, "big")
            left_den_bytes = left.denominator.to_bytes((left.denominator.bit_length() + 7) // 8 or 1, "big")
            right_num_bytes = right.numerator.to_bytes((right.numerator.bit_length() + 7) // 8 or 1, "big")
            right_den_bytes = right.denominator.to_bytes((right.denominator.bit_length() + 7) // 8 or 1, "big")
            
            # Write length prefixes and data
            f.write(len(left_num_bytes).to_bytes(1, "big"))
            f.write(left_num_bytes)
            f.write(len(left_den_bytes).to_bytes(1, "big"))
            f.write(left_den_bytes)
            f.write(len(right_num_bytes).to_bytes(1, "big"))
            f.write(right_num_bytes)
            f.write(len(right_den_bytes).to_bytes(1, "big"))
            f.write(right_den_bytes)
    
    print(f"✓ Compressed data saved to {output_file}")
    
    return original_size, keystone_data


def decompress_file(input_file, output_file):
    """
    Decompress a file by recovering original 2-bit values from fraction pairs.
    """
    with open(input_file, "rb") as f:
        original_size = int.from_bytes(f.read(4), "big")
        total_2bit_values = int.from_bytes(f.read(4), "big")
        
        recovered_values = []
        n = 4
        
        while len(recovered_values) < total_2bit_values:
            try:
                # Read fraction data
                left_num_len = int.from_bytes(f.read(1), "big")
                left_num = int.from_bytes(f.read(left_num_len), "big")
                left_den_len = int.from_bytes(f.read(1), "big")
                left_den = int.from_bytes(f.read(left_den_len), "big")
                right_num_len = int.from_bytes(f.read(1), "big")
                right_num = int.from_bytes(f.read(right_num_len), "big")
                right_den_len = int.from_bytes(f.read(1), "big")
                right_den = int.from_bytes(f.read(right_den_len), "big")
                
                right = Fraction(right_num, right_den)
                
                # Recover v by testing all 4 possible values
                found = False
                for v in range(4):
                    _, expected_right = keystone_pair_exact(v, n)
                    if expected_right == right:
                        recovered_values.append(v)
                        found = True
                        break
                
                if not found:
                    raise ValueError(f"Could not recover 2-bit value from right={right}")
            
            except:
                break
    
    print(f"Decompressing {len(recovered_values)} keystone pairs...")
    print(f"Original size: {original_size} bytes")
    
    # Reconstruct bytes from 2-bit values
    recovered_data = two_bit_values_to_bytes(recovered_values)
    recovered_data = recovered_data[:original_size]
    
    # Write decompressed data
    with open(output_file, "wb") as f:
        f.write(recovered_data)
    
    print(f"✓ Recovered {len(recovered_data)} bytes")
    
    return recovered_data


def test_compression():
    """Test compression and decompression on sample data."""
    
    print("=" * 80)
    print("KEYSTONE FILE COMPRESSION TEST (2 BITS AT A TIME - ACTUAL FRACTIONS)")
    print("=" * 80)
    print()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        original_file = os.path.join(tmpdir, "original.txt")
        compressed_file = os.path.join(tmpdir, "compressed.bin")
        decompressed_file = os.path.join(tmpdir, "decompressed.txt")
        
        test_data = b"Hello, World! This is a keystone compression test. " * 3
        
        print(f"Original data: {test_data[:50]}...")
        print(f"Original data length: {len(test_data)} bytes")
        print()
        
        with open(original_file, "wb") as f:
            f.write(test_data)
        
        # Compress
        print("COMPRESSION STEP:")
        print("-" * 80)
        orig_size, keystone_data = compress_file(original_file, compressed_file)
        
        print("\n" + "=" * 80)
        print("EXAMINING FRACTION VALUES")
        print("-" * 80)
        print("\nFirst 10 keystone pairs (v, left fraction, right fraction):")
        for item in keystone_data[:10]:
            print(f"  v={item['v']} | left={item['left_numerator']}/{item['left_denominator']} "
                  f"({item['left_decimal']:.6f}) | "
                  f"right={item['right_numerator']}/{item['right_denominator']} "
                  f"({item['right_decimal']:.6f})")
        
        print("\n" + "=" * 80)
        print("DECOMPRESSION STEP:")
        print("-" * 80)
        recovered = decompress_file(compressed_file, decompressed_file)
        
        # Verify
        print("\n" + "=" * 80)
        print("VERIFICATION:")
        print("-" * 80)
        
        with open(decompressed_file, "rb") as f:
            recovered_data = f.read()
        
        if recovered_data == test_data:
            print("✓ PERFECT MATCH - Decompressed data matches original!")
        else:
            print("✗ MISMATCH - Data corruption detected!")


if __name__ == "__main__":
    test_compression()
