#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <string>
#include <vector>

using namespace std;

struct Job {
  int id;
  vector<double> means;
  vector<double> stds;
};

class ProblemInstance {
 public:
  int n_jobs;
  int n_machines;
  vector<Job> jobs;

  bool loadFromFile(const string& filename) {
    ifstream file(filename);
    if (!file.is_open()) return false;

    if (!(file >> n_jobs >> n_machines)) return false;

    jobs.resize(n_jobs);

    for (int i = 0; i < n_jobs; i++) {
      jobs[i].id = i;
      jobs[i].means.resize(n_machines);
      for (int j = 0; j < n_machines; j++) {
        file >> jobs[i].means[j];
      }
    }

    for (int i = 0; i < n_jobs; i++) {
      jobs[i].stds.resize(n_machines);
      for (int j = 0; j < n_machines; j++) {
        file >> jobs[i].stds[j];
      }
    }
    return true;
  }
};

double estimateMakespan(const ProblemInstance& inst,
                        const vector<int>& permutation, int samples = 50) {
  static mt19937 rng(42);
  double totalMakespan = 0.0;

  for (int k = 0; k < samples; k++) {
    vector<double> machineFreeTime(inst.n_machines, 0.0);

    for (int jobIdx : permutation) {
      const Job& job = inst.jobs[jobIdx];

      double prevMachineFinishTime = 0.0;

      for (int m = 0; m < inst.n_machines; m++) {
        normal_distribution<double> dist(job.means[m], job.stds[m]);
        double processingTime = dist(rng);
        if (processingTime < 0.001) processingTime = 0.001;

        double startTime = max(machineFreeTime[m], prevMachineFinishTime);

        machineFreeTime[m] = startTime + processingTime;
        prevMachineFinishTime = machineFreeTime[m];
      }
    }

    totalMakespan += machineFreeTime.back();
  }

  return totalMakespan / samples;
}

double calculateInitialTemperature(const ProblemInstance& inst, vector<int>& p,
                                   double initialCost) {
  return initialCost * 0.05;
}

vector<int> simulatedAnnealing(const ProblemInstance& inst) {
  vector<int> currentSol(inst.n_jobs);
  iota(currentSol.begin(), currentSol.end(), 0);

  int mcSamplesFast = 30;

  double currentCost = estimateMakespan(inst, currentSol, mcSamplesFast);

  vector<int> bestSol = currentSol;
  double bestCost = currentCost;

  double T = calculateInitialTemperature(inst, currentSol, currentCost);
  double T_end = 0.1;
  double alpha = 0.97;
  int iterPerTemp = 100;

  mt19937 rng(random_device{}());
  uniform_real_distribution<double> dist01(0.0, 1.0);
  uniform_int_distribution<int> distIdx(0, inst.n_jobs - 1);

  cout << "Start SA. Koszt poczatkowy: " << currentCost << ", T0: " << T
       << endl;

  while (T > T_end) {
    for (int i = 0; i < iterPerTemp; i++) {
      vector<int> neighbor = currentSol;
      int a = distIdx(rng);
      int b = distIdx(rng);
      swap(neighbor[a], neighbor[b]);

      double neighborCost = estimateMakespan(inst, neighbor, mcSamplesFast);

      double delta = neighborCost - currentCost;

      bool accept = false;
      if (delta < 0) {
        accept = true;
      } else {
        double probability = exp(-delta / T);
        if (dist01(rng) < probability) {
          accept = true;
        }
      }

      if (accept) {
        currentSol = neighbor;
        currentCost = neighborCost;

        if (currentCost < bestCost) {
          bestCost = currentCost;
          bestSol = currentSol;
          cout << "Nowy rekord: " << bestCost << " (T=" << T << ")" << endl;
        }
      }
    }

    T *= alpha;
  }

  return bestSol;
}

int main(int argc, char* argv[]) {
  string filename;

  if (argc < 2) {
    cerr << "Użycie: " << (argc ? argv[0] : "program") << " <plik_wejsciowy>"
         << endl;
    return 1;
  }

  filename = argv[1];
  ProblemInstance problem;

  cout << "Wczytywanie danych z " << filename << "..." << endl;
  if (!problem.loadFromFile(filename)) {
    cerr << "Blad: Nie znaleziono pliku!" << endl;
    return 1;
  }

  cout << "Zaladowano instancje: " << problem.n_jobs << " zadan, "
       << problem.n_machines << " maszyn." << endl;

  vector<int> bestPermutation = simulatedAnnealing(problem);

  double finalResult = estimateMakespan(problem, bestPermutation, 1000);

  cout << "\n--- WYNIKI ---" << endl;
  cout << "Najlepszy znaleziony Makespan (estymowany): " << finalResult << endl;
  cout << "Kolejnosc zadan: ";
  for (int id : bestPermutation) {
    cout << id << " ";
  }
  cout << endl;

  return 0;
}