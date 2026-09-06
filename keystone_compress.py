#!/usr/bin/env python3
"""
Keystone-based file compression/decompression.

Compression processes 2 bits at a time, creating a keystone pair for each 2-bit value.
Decompression recovers both 'left' and 'right' from stored 'right' values.
"""

from keystone import (
    keystone_pair_exact,
    fractions_to_dense,
    dense_to_fractions,
)
from fractions import Fraction
import tempfile
import os


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
        - Use n = 4 (power of 2, fixed denominator)
        - Store only the 'right' fraction from keystone_pair_exact(v, n)
    
    This stores minimal data and allows full recovery of both left and right.
    """
    with open(input_file, "rb") as f:
        data = f.read()
    
    original_size = len(data)
    total_bits = original_size * 8
    total_2bit_values = (total_bits + 1) // 2  # Round up
    
    print(f"Compressing {original_size} bytes ({total_bits} bits)...")
    print(f"Processing 2 bits at a time → {total_2bit_values} keystone pairs")
    
    # Extract 2-bit values
    two_bit_values = bits_to_2bit_values(data)
    
    right_fractions = []
    n = 4  # Fixed denominator for 2-bit values (0-3)
    
    # Generate keystone pair for each 2-bit value
    for v in two_bit_values:
        left, right = keystone_pair_exact(v, n)
        right_fractions.append(right)
    
    # Encode all 'right' fractions
    encoded = fractions_to_dense(right_fractions)
    
    print(f"  Original size: {original_size} bytes")
    print(f"  Compressed size: {len(encoded)} bytes")
    print(f"  Compression ratio: {len(encoded) / original_size:.2%}")
    
    # Write compressed data with metadata
    with open(output_file, "wb") as f:
        # Write original size (4 bytes)
        f.write(original_size.to_bytes(4, "big"))
        # Write number of 2-bit values (4 bytes)
        f.write(total_2bit_values.to_bytes(4, "big"))
        # Write compressed fractions
        f.write(encoded)
    
    return original_size, len(encoded), total_2bit_values


def decompress_file(input_file, output_file):
    """
    Decompress a file by recovering original 2-bit values from stored 'right' fractions.
    
    For each stored 'right' fraction, recover v by finding which value (0-3)
    produces that exact 'right' fraction.
    """
    with open(input_file, "rb") as f:
        original_size = int.from_bytes(f.read(4), "big")
        total_2bit_values = int.from_bytes(f.read(4), "big")
        encoded = f.read()
    
    # Decode the stored 'right' fractions
    right_fractions = dense_to_fractions(encoded)
    
    print(f"Decompressing {len(right_fractions)} keystone pairs...")
    print(f"Original size: {original_size} bytes")
    print(f"Total 2-bit values: {total_2bit_values}")
    
    recovered_values = []
    n = 4  # Same n used during compression
    
    # For each stored 'right' fraction, recover the original 2-bit value
    for i, right in enumerate(right_fractions):
        found = False
        
        # Try all 4 possible 2-bit values (0-3)
        for v in range(4):
            _, expected_right = keystone_pair_exact(v, n)
            
            if expected_right == right:
                recovered_values.append(v)
                found = True
                break
        
        if not found:
            raise ValueError(f"Could not recover 2-bit value {i} from right={right}")
    
    # Reconstruct bytes from 2-bit values
    recovered_data = two_bit_values_to_bytes(recovered_values)
    
    # Trim to original size (in case of padding)
    recovered_data = recovered_data[:original_size]
    
    # Write decompressed data
    with open(output_file, "wb") as f:
        f.write(recovered_data)
    
    print(f"  Total recovered: {len(recovered_data)} bytes")
    
    if len(recovered_data) != original_size:
        print(f"  WARNING: Size mismatch - expected {original_size}, got {len(recovered_data)}")
    
    return recovered_data


def test_compression():
    """Test compression and decompression on sample data."""
    
    print("=" * 80)
    print("KEYSTONE FILE COMPRESSION/DECOMPRESSION TEST (2 BITS AT A TIME)")
    print("=" * 80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        original_file = os.path.join(tmpdir, "original.txt")
        compressed_file = os.path.join(tmpdir, "compressed.bin")
        decompressed_file = os.path.join(tmpdir, "decompressed.txt")
        
        test_data = b"Hello, World! This is a keystone compression test. " * 3
        
        print(f"\nOriginal data: {test_data[:50]}...")
        print(f"Original data length: {len(test_data)} bytes\n")
        
        with open(original_file, "wb") as f:
            f.write(test_data)
        
        # Compress
        print("COMPRESSION STEP:")
        print("-" * 80)
        orig_size, comp_size, num_pairs = compress_file(original_file, compressed_file)
        
        # Decompress
        print("\nDECOMPRESSION STEP:")
        print("-" * 80)
        recovered = decompress_file(compressed_file, decompressed_file)
        
        # Verify
        print("\nVERIFICATION:")
        print("-" * 80)
        
        with open(decompressed_file, "rb") as f:
            recovered_data = f.read()
        
        if recovered_data == test_data:
            print("✓ PERFECT MATCH - Decompressed data matches original!")
        else:
            print("✗ MISMATCH - Data corruption detected!")
            print(f"  Original:     {test_data[:50]}")
            print(f"  Decompressed: {recovered_data[:50]}")
            
            # Show first difference
            for i, (a, b) in enumerate(zip(test_data, recovered_data)):
                if a != b:
                    print(f"  First difference at byte {i}: {a:08b} vs {b:08b}")
                    break
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("-" * 80)
        print(f"Original size:        {orig_size:6d} bytes ({orig_size * 8:6d} bits)")
        print(f"Compressed size:      {comp_size:6d} bytes")
        print(f"Compression ratio:    {comp_size / orig_size:6.2%}")
        print(f"Keystone pairs:       {num_pairs:6d} (one per 2 bits)")
        print(f"Storage method:       2-bit values (0-3) → keystone 'right' fractions")
        print("=" * 80)


if __name__ == "__main__":
    test_compression()
