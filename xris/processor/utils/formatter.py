import csv

class TranslateFormat:
    @staticmethod
    def to_ssv(csv_path: str, ssv_path: str):
        """
        Converts a comma-separated values (CSV) file into a space-separated values (SSV) file.
        """
        try:
            with open(csv_path, mode="r", newline="", encoding="utf-8") as csv_file, \
                 open(ssv_path, mode="w", newline="", encoding="utf-8") as ssv_file:

                reader = csv.reader(csv_file)
                writer = ssv_file.write

                for row in reader:
                    writer(" ".join(row) + "\n")
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {csv_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to convert CSV to SSV: {e}")
