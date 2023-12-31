from pathlib import Path
import pandas as pd
import requests
import numpy as np
import json
import shutil
import time
import scipy.spatial

def download_file(url, save_path):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"Pobrano i zapisano plik jako {save_path}")
    else:
        print(f"Wystąpił błąd podczas pobierania pliku {save_path}")

def read_obj_file(path: str):

    #Function to read .obj files and return vertices and faces as lists

    vertices = []
    faces = []
    texture_vertices = []

    with open(path, "r") as f:

        for line in f:
            if line.startswith('v'):
                line.split(' ')
                line = line[1:].split()
                for i in range(3):
                    line[i] = float(line[i])
                vertices.append(line)
            elif line.startswith('f'):
                line.split(' ')
                line = line[1:].split()
                for i in range(4):
                    line[i] = int(line[i])
                faces.append(line)
            elif line.startswith('vt'):
                pass
                #TODO: implement texture vertices?
            elif line.startswith('#') or line.startswith(' ') or line.startswith('/n'):
                pass
            else:
                pass

    return vertices, faces


def read_stl_file(path: str, return_normals=False):

    #Function to read .stl files and return vertices and faces as lists. Also returns normals if return_normals=True

    vertices = []
    faces = []
    normals = []

    with open(path, "r") as f:

        for line in f:
            if line.strip().startswith('vertex'):
                vertex = [float(coord) for coord in line.strip().split()[1:]]
                vertices.append(vertex)
            elif line.strip().startswith('endloop'): #saving face after reading 3 vertices
                face = [len(vertices) - 3, len(vertices) - 2, len(vertices) - 1]
                faces.append(face)
            elif line.strip().startswith('facet normal'):
                normal = [float(coord) for coord in line.strip().split()[2:]]
                normals.append(normal)
    
    if return_normals:
        return vertices, faces, normals
    else:
        return vertices, faces
    

class Mesh:

    def __init__(self, path: str): #TODO: rozbić na dwie klasy (stl i obj), przeciążające klasę Mesh
        if path.suffix == '.obj':
            self.vertices, self.faces = read_obj_file(path)
            self.fileformat = 'obj'
        elif path.suffix == '.stl':
            self.vertices, self.faces, self.normals = read_stl_file(path, return_normals=True)
            self.fileformat = 'stl'
        else:
            raise ValueError('Unsupported file format. Supported formats are .obj and .stl. Format you tried to use is: ', path.suffix)
        self.path = path
        self.triangle_mesh = self.triangulate_faces()
    
    def triangulate_faces(self):
        if self.fileformat == 'stl':
            return self.faces
        else:
            triangles = []
            for face in self.faces:
                # Sprawdzamy, czy to jest wielokąt (więcej niż 3 wierzchołki)
                if len(face) > 3:
                    # Tworzymy trójkąty przez dzielenie wielokąta na kolejne trójkąty
                    for i in range(1, len(face) - 1):
                        triangle = [face[0]-1, face[i]-1, face[i + 1]-1]
                        triangles.append(triangle)
                else:
                    # Jeśli to jest trójkąt, po prostu dodajemy go do listy trójkątów
                    triangles.append(face)
            self.triangles = triangles
            return triangles
    
    def get_triangulated_faces(self):
        return self.triangle_mesh

    def get_vertices(self):
        return self.vertices
    
    def get_faces(self):
        return self.faces
    
    def get_path(self):
        return self.path
    
    def get_corners(self):
        corners = []

        for face in self.faces:
            if len(face) == 3:
                # W przypadku trójkątów (STL) dodajemy je bezpośrednio do corners
                triangle = [self.vertices[int(vertex_index)] for vertex_index in face]
                corners.append(triangle)
            elif len(face) > 3:
                # W przypadku wielokątów (OBJ) dzielimy je na kolejne trójkąty
                for i in range(1, len(face) - 1):
                    triangle = [self.vertices[int(face[0]) -1], self.vertices[int(face[i]) -1], self.vertices[int(face[i + 1]) -1]] #-1, bo indeksowanie od 1 w obj
                    corners.append(triangle)

        return corners

    def get_normals(self):
        normals = []
        for face in self.triangle_mesh:
            normal = self.calculate_normal(self.vertices, face)
            normals.append(normal)
        return normals
    
    def get_centers(self):

        centers = []

        for face in self.triangle_mesh:
            sum = [0, 0, 0]
            for vertex in face:
                sum[0] += self.vertices[vertex][0]
                sum[1] += self.vertices[vertex][1]
                sum[2] += self.vertices[vertex][2]
            center = [coord / 3 for coord in sum]
            centers.append(center)

        return centers
    
    def get_neighbors(self):
        start = time.time()
        faces_contain_this_vertex = []
        for i in range(len(self.vertices)):
            faces_contain_this_vertex.append(set([]))
        for i in range(len(self.faces)):
            [v1, v2, v3] = self.faces[i]
            x1, y1, z1 = self.vertices[v1]
            x2, y2, z2 = self.vertices[v2]
            x3, y3, z3 = self.vertices[v3]
            faces_contain_this_vertex[v1].add(i)
            faces_contain_this_vertex[v2].add(i)
            faces_contain_this_vertex[v3].add(i)

        neighbors = []
        for i in range(len(self.faces)):
            [v1, v2, v3] = self.faces[i]
            
            n1 = self.find_neighbor(faces_contain_this_vertex, v1, v2, i)
            n2 = self.find_neighbor(faces_contain_this_vertex, v2, v3, i)
            n3 = self.find_neighbor(faces_contain_this_vertex, v3, v1, i)
            
            neighbors.append([n1, n2, n3])
        stop = time.time()
        print("Time of finding neighbors: ", stop - start)
        return neighbors

    def find_neighbor(self, faces_contain_this_vertex, vf1, vf2, except_face):
        for i in (faces_contain_this_vertex[vf1] & faces_contain_this_vertex[vf2]):
            if i != except_face:
                face = self.faces[i].tolist()
                print(face)
                face.remove(vf1) #TODO: zmienić metodę żeby nie było tylu operacji na listach. Also, zrobić to z numpy dla przyspieszenia
                face.remove(vf2)
                print(face)
                return i

        return except_face

    def calculate_normal(self, vertices, triangle):
        # Obliczamy wektor różnicy dla dwóch kolejnych punktów
        edge1 = [vertices[triangle[1]][j] - vertices[triangle[0]][j] for j in range(3)]
        edge2 = [vertices[triangle[2]][j] - vertices[triangle[0]][j] for j in range(3)]

        # Obliczamy iloczyn wektorowy dwóch krawędzi
        cross_product = [
            edge1[1] * edge2[2] - edge1[2] * edge2[1],
            edge1[2] * edge2[0] - edge1[0] * edge2[2],
            edge1[0] * edge2[1] - edge1[1] * edge2[0]
        ]

        # Normalizujemy wektor normalny (zmniejszamy jego długość do 1)
        normal_length = (cross_product[0]**2 + cross_product[1]**2 + cross_product[2]**2)**0.5
        normal = [coord / normal_length for coord in cross_product]

        return normal    

def prepare_data(csv_file):
    #Main folder path
    parent_folder = Path(__file__).resolve().parent.parent
    print(parent_folder)
    dataset_folder = parent_folder / 'dataset'
    meshes_folder = dataset_folder / 'meshes'
    meshes_folder.mkdir(parents=True, exist_ok=True)
    numpy_folder = dataset_folder / 'data'
    numpy_folder.mkdir(parents=True, exist_ok=True)

    print("Preparing CSV file to read data...")
    dataset = pd.read_csv(csv_file)

    shutil.copy(csv_file, dataset_folder / 'summary.csv')

    print("CSV file ready!")

    print("Starting data preparation...")

    for index, row in dataset.iterrows():
        start = time.time()
        print("id: ", row['id'], "link: ", row['link'])
        filename = "mesh_" + str(row['id']) + ".stl"
        mesh_file = meshes_folder / filename
        download_file(row['link'], mesh_file)
        mesh = Mesh(mesh_file)
        mesh_folder = numpy_folder / str(row['id'])
        mesh_folder.mkdir(parents=True, exist_ok=True)
        np.save(mesh_folder / 'vertices.npy', mesh.get_vertices())
        np.save(mesh_folder / 'faces.npy', mesh.get_faces())
        np.save(mesh_folder / 'triangles.npy', mesh.get_triangulated_faces())
        np.save(mesh_folder / 'corners.npy', mesh.get_corners())
        np.save(mesh_folder / 'centers.npy', mesh.get_centers())
        np.save(mesh_folder / 'normals.npy', mesh.get_normals())
        np.save(mesh_folder / 'neighbors.npy', mesh.get_neighbors())
        json_filename = str(row['id']) + '.json'
        json_file = dataset_folder / json_filename
        json_content = {"name" : filename,
                        "class" : row['item'],
                        "link" : row['link'],
                        "vertices" : str(mesh_folder / 'vertices.npy'),
                        "faces" : str(mesh_folder / 'faces.npy'),
                        "triangles" : str(mesh_folder / 'triangles.npy'),
                        "corners" : str(mesh_folder / 'corners.npy'),
                        "centers" : str(mesh_folder / 'centers.npy'),
                        "normals" : str(mesh_folder / 'normals.npy'),
                        "neighbors" : str(mesh_folder / 'neighbors.npy'),
                        "mesh" : str(mesh_file)
                        }
        json_content = json.dumps(json_content)
        with json_file.open('w') as f:
            f.write(json_content)
        print("Zapisano plik json")
        stop = time.time()
        print("Czas operacji: ", stop - start)


if __name__ == "__main__":
    CSV = 'dataset.csv'
    prepare_data(CSV)