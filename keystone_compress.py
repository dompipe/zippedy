#!/usr/bin/env python3
"""
Keystone-based file compression/decompression.

Compression groups data into chunks and stores only the 'right' fraction.
Decompression recovers both 'left' and 'right' from just 'right' using mathematical relationships.
"""

from keystone import (
    keystone_pair_exact,
    fractions_to_dense,
    dense_to_fractions,
)
from fractions import Fraction
import tempfile
import os


def bytes_to_int(data: bytes) -> int:
    """Convert bytes to a single integer."""
    return int.from_bytes(data, "big")


def int_to_bytes(value: int, length: int) -> bytes:
    """Convert integer to bytes with specified length."""
    return value.to_bytes(length, "big")


def compress_file(input_file, output_file, chunk_size=None):
    """
    Compress a file by treating entire content as one or more chunks.
    
    For each chunk of data:
        - Treat the entire chunk as a single integer v
        - Use n = 256 (or configurable)
        - Store only the 'right' fraction from keystone_pair_exact(v, n)
    
    This stores minimal data and allows full recovery of both left and right.
    """
    with open(input_file, "rb") as f:
        data = f.read()
    
    original_size = len(data)
    
    # If no chunk size specified, use entire file as one chunk
    if chunk_size is None:
        chunk_size = original_size
    
    print(f"Compressing {original_size} bytes...")
    print(f"Chunk size: {chunk_size} bytes per keystone pair")
    
    right_fractions = []
    n = 256  # Fixed denominator for all pairs
    chunk_count = 0
    
    # Process data in chunks
    pos = 0
    while pos < original_size:
        # Get chunk
        end = min(pos + chunk_size, original_size)
        chunk = data[pos:end]
        
        # Convert chunk to integer v
        v = bytes_to_int(chunk)
        
        # Generate keystone pair and keep only 'right' fraction
        left, right = keystone_pair_exact(v, n)
        right_fractions.append(right)
        chunk_count += 1
        
        pos = end
    
    # Encode all 'right' fractions
    encoded = fractions_to_dense(right_fractions)
    
    print(f"  Chunks: {chunk_count}")
    print(f"  Original size: {original_size} bytes")
    print(f"  Compressed size: {len(encoded)} bytes")
    print(f"  Compression ratio: {len(encoded) / original_size:.2%}")
    
    # Write compressed data with metadata
    with open(output_file, "wb") as f:
        # Write original size (4 bytes)
        f.write(original_size.to_bytes(4, "big"))
        # Write chunk size (4 bytes)
        f.write(chunk_size.to_bytes(4, "big"))
        # Write compressed fractions
        f.write(encoded)
    
    return original_size, len(encoded), chunk_count


def decompress_file(input_file, output_file):
    """
    Decompress a file by recovering original bytes from stored 'right' fractions.
    
    Given: right = b/n + v, where b = int(binary(v) as decimal) and n = 256
    
    We solve for v by trying to reconstruct it from the 'right' value.
    """
    with open(input_file, "rb") as f:
        original_size = int.from_bytes(f.read(4), "big")
        chunk_size = int.from_bytes(f.read(4), "big")
        encoded = f.read()
    
    # Decode the stored 'right' fractions
    right_fractions = dense_to_fractions(encoded)
    
    print(f"Decompressing {len(right_fractions)} keystone pairs...")
    print(f"Original size: {original_size} bytes")
    print(f"Chunk size: {chunk_size} bytes")
    
    recovered_data = bytearray()
    n = 256  # Same n used during compression
    
    # For each stored 'right' fraction, recover the original chunk
    for i, right in enumerate(right_fractions):
        found = False
        
        # Determine max value for this chunk
        if i == len(right_fractions) - 1:
            # Last chunk might be smaller
            remaining = original_size - (i * chunk_size)
            max_val = (1 << (remaining * 8)) - 1
        else:
            max_val = (1 << (chunk_size * 8)) - 1
        
        # Try to recover v from right value
        # This is a brute force approach for small chunks
        # For larger chunks, we'd need a more sophisticated method
        
        # Use binary search or mathematical solving
        # For now, simple approach: iterate through possible values
        
        # Better approach: given right = b/n + v, solve algebraically
        # right - v = b/n, where b = int(binary(v) as decimal)
        # This is hard to solve directly, so we use an iterative approach
        
        # For reasonable chunk sizes, we can narrow the search
        # Start with the integer part of right as an estimate
        estimate = int(right)
        
        # Search around the estimate
        search_range = max(1000, chunk_size * 10)
        for v in range(max(0, estimate - search_range), estimate + search_range + 1):
            if v > max_val:
                break
            
            _, expected_right = keystone_pair_exact(v, n)
            
            if expected_right == right:
                # Recover the chunk
                chunk_len = len(right_fractions[-1:]) if i == len(right_fractions) - 1 else chunk_size
                if i == len(right_fractions) - 1:
                    chunk_len = original_size - (i * chunk_size)
                
                chunk_bytes = int_to_bytes(v, chunk_len)
                recovered_data.extend(chunk_bytes)
                found = True
                print(f"  ✓ Chunk {i}: recovered {len(chunk_bytes)} bytes")
                break
        
        if not found:
            print(f"  ✗ Chunk {i}: Could not recover from right={right}")
            raise ValueError(f"Could not recover original chunk {i} from right={right}")
    
    # Write decompressed data
    with open(output_file, "wb") as f:
        f.write(bytes(recovered_data))
    
    print(f"  Total recovered: {len(recovered_data)} bytes")
    
    if len(recovered_data) != original_size:
        print(f"  WARNING: Size mismatch - expected {original_size}, got {len(recovered_data)}")
    
    return recovered_data


def test_compression():
    """Test compression and decompression on sample data."""
    
    print("=" * 80)
    print("KEYSTONE FILE COMPRESSION/DECOMPRESSION TEST (ALL 153 BYTES)")
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
        
        # Compress with full file as one chunk
        print("COMPRESSION STEP:")
        print("-" * 80)
        orig_size, comp_size, chunks = compress_file(original_file, compressed_file, chunk_size=len(test_data))
        
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
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("-" * 80)
        print(f"Original size:     {orig_size:6d} bytes")
        print(f"Compressed size:   {comp_size:6d} bytes")
        print(f"Ratio:             {comp_size / orig_size:6.2%}")
        print(f"Storage method:    All {orig_size} bytes as single keystone 'right' fraction")
        print("=" * 80)


if __name__ == "__main__":
    test_compression()
