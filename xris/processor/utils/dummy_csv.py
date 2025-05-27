import csv
import numpy as np

def generate_dummy_csv(filename="mesh_data.csv", x_dim=602, y_dim=602):
    data = np.random.uniform(0, 100, size=(x_dim, y_dim))
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(data)
    return filename
