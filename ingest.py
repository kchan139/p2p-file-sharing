def write_file_contents(output_file):
    """
    Writes the contents of specific files to the output file in the desired format.

    Args:
        output_file (str): The name of the file to write the contents to.
    """
    files_to_read = [
        "./data", 
        "./src/config.py",
        "./src/node.py",
        "./src/torrent.py",
        "./src/tracker.py",
        "./src/utils.py",
        "./tests/unit_test.py",
        "./reference/code/client.py",
        "./reference/code/deal_torrent.py",
        "./reference/code/merge.py",
        "./reference/code/tracker.py",
        "./reference/code/metainfo.torrent",
        "./reference/docs/HK241_Assignment1.md",
    ]

    with open(output_file, "w", encoding="utf-8") as f:
        for file_path in files_to_read:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    # Write file separator and name
                    f.write(f"================================================\n")
                    f.write(f"File: {file_path}\n")
                    f.write(f"================================================\n")
                    # Write content
                    f.write(file.read())
                    f.write("\n\n")
            except FileNotFoundError:
                f.write(f"================================================\n")
                f.write(f"File: {file_path}\n")
                f.write(f"================================================\n")
                f.write("File not found.\n\n")
            except Exception as e:
                f.write(f"================================================\n")
                f.write(f"File: {file_path}\n")
                f.write(f"================================================\n")
                f.write(f"Error reading file: {e}\n\n")

# Specify the output file name
output_filename = "local.txt"

# Write the contents to local.txt
write_file_contents(output_filename)
print(f"File contents have been written to {output_filename}.")
