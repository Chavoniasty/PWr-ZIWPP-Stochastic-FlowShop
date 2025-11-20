import random

"""
Format danych:
Liczba_zadan Liczba_maszyn

Średnie (macierz n_jobs x n_machines)

Odchylenie standardowe (macierz n_jobs x n_machines)
"""

def generate_sfsp_instance(filename, n_jobs, n_machines): 
    print(f"Generowanie instancji: {n_jobs} zadan, {n_machines} maszyn -> {filename}")
    
    with open(filename, 'w') as f:
        f.write(f"{n_jobs} {n_machines}\n")

        f.write("\n")
        for _ in range(n_jobs):
            row = []
            for _ in range(n_machines):
                val = random.randint(10, 100)
                row.append(str(val))
            f.write(" ".join(row) + "\n")
            
        f.write("\n")
        for r in range(n_jobs):
            row = []
            for _ in range(n_machines):
               
               val = random.uniform(0.5, 5.0) 
               row.append(f"{val:.2f}")
            f.write(" ".join(row) + "\n")

if __name__ == "__main__":
    generate_sfsp_instance("dane_male.txt", n_jobs=5, n_machines=3)
    generate_sfsp_instance("dane_srednie.txt", n_jobs=20, n_machines=5)
    generate_sfsp_instance("dane_duze.txt", n_jobs=50, n_machines=10)