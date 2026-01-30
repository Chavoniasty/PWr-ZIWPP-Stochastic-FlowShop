#include <algorithm>
#include <cmath>
#include <iostream>
#include <numeric>
#include <random>
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

    void loadFromArrays(int jobs_count, int machines_count, double* flat_means, double* flat_stds) {
        n_jobs = jobs_count;
        n_machines = machines_count;
        jobs.resize(n_jobs);
        for (int i = 0; i < n_jobs; i++) {
            jobs[i].id = i;
            jobs[i].means.resize(n_machines);
            jobs[i].stds.resize(n_machines);
            for (int j = 0; j < n_machines; j++) {
                int idx = i * n_machines + j;
                jobs[i].means[j] = flat_means[idx];
                jobs[i].stds[j]  = flat_stds[idx];
            }
        }
    }
};

typedef void (*StatusCallback)(int*, double, double*);

void calculateSchedule(const ProblemInstance &inst, const vector<int> &permutation, double* output) {
    vector<double> machineFreeTime(inst.n_machines, 0.0);

    for (int jobIdx : permutation) {
        const Job &job = inst.jobs[jobIdx];
        double prevMachineFinishTime = 0.0;

        for (int m = 0; m < inst.n_machines; m++) {
            double processingTime = max(0.001, job.means[m]);
            double startTime = max(machineFreeTime[m], prevMachineFinishTime);
            double endTime = startTime + processingTime;

            machineFreeTime[m] = endTime;
            prevMachineFinishTime = endTime;

            int baseIdx = (job.id * inst.n_machines + m) * 2;
            output[baseIdx]     = startTime;
            output[baseIdx + 1] = endTime;
        }
    }
}

double estimateMakespan(const ProblemInstance &inst, const vector<int> &permutation, int samples, bool isCtg) {
    mt19937 rng(42);
    double totalMakespan = 0.0;
    for (int k = 0; k < samples; k++) {
        vector<double> machineFreeTime(inst.n_machines, 0.0);
        for (int jobIdx : permutation) {
            const Job &job = inst.jobs[jobIdx];
            double prevMachineFinishTime = 0.0;
            for (int m = 0; m < inst.n_machines; m++) {
                double val = isCtg ? job.means[m] : normal_distribution<double>(job.means[m], job.stds[m])(rng);
                double processingTime = max(0.001, val);
                double startTime = max(machineFreeTime[m], prevMachineFinishTime);
                machineFreeTime[m] = startTime + processingTime;
                prevMachineFinishTime = machineFreeTime[m];
            }
        }
        totalMakespan += machineFreeTime.back();
    }
    return totalMakespan / samples;
}

double estimateMakespanForJob(const ProblemInstance &inst, int jobId, int samples, bool isCtg) {
    const Job &job = inst.jobs[jobId];
    double sum = 0.0;
    mt19937 rng(42);
    for (int k = 0; k < (isCtg ? 1 : samples); k++) {
        for (int m = 0; m < inst.n_machines; m++) {
            double val = isCtg ? job.means[m] : normal_distribution<double>(job.means[m], job.stds[m])(rng);
            sum += max(0.001, val);
        }
    }
    return sum / (isCtg ? 1 : samples);
}

void reportProgress(const ProblemInstance &inst, const vector<int>& sol, double cost, StatusCallback cb) {
    if (!cb) return;
    vector<int> reportSol = sol;
    for(auto& x : reportSol) x++;

    vector<double> sched(inst.n_jobs * inst.n_machines * 2);
    calculateSchedule(inst, sol, sched.data());

    cb(reportSol.data(), cost, sched.data());
}

vector<int> simulatedAnnealing(const ProblemInstance &inst, int mcSamples, bool isCtg, double* params, StatusCallback cb) {
    vector<int> currentSol(inst.n_jobs);
    iota(currentSol.begin(), currentSol.end(), 0);

    double currentCost = estimateMakespan(inst, currentSol, mcSamples, isCtg);
    vector<int> bestSol = currentSol;
    double bestCost = currentCost;

    reportProgress(inst, bestSol, bestCost, cb);

    // Pobieranie parametrów przekazanych z Pythona
    // params[0] = Temperatura początkowa (jeśli 0, to oblicz automatycznie)
    // params[1] = Współczynnik chłodzenia (Alpha)
    // params[2] = Iteracje na temperaturę
    
    double T = (params[0] > 0) ? params[0] : (currentCost * 0.05); // Default lub Custom
    double alpha = (params[1] > 0) ? params[1] : 0.97;
    int iterPerTemp = (params[2] > 0) ? (int)params[2] : 100;
    double T_end = 0.1;

    mt19937 rng(random_device{}());
    uniform_real_distribution<double> dist01(0.0, 1.0);
    uniform_int_distribution<int> distIdx(0, inst.n_jobs - 1);

    while (T > T_end) {
        for (int i = 0; i < iterPerTemp; i++) {
            vector<int> neighbor = currentSol;
            // Prosta zamiana dwóch losowych zadań
            swap(neighbor[distIdx(rng)], neighbor[distIdx(rng)]);
            
            double neighborCost = estimateMakespan(inst, neighbor, mcSamples, isCtg);
            double delta = neighborCost - currentCost;

            if (delta < 0 || dist01(rng) < exp(-delta / T)) {
                currentSol = neighbor;
                currentCost = neighborCost;

                if (currentCost < bestCost) {
                    bestCost = currentCost;
                    bestSol = currentSol;
                    reportProgress(inst, bestSol, bestCost, cb);
                }
            }
        }
        T *= alpha;
    }
    return bestSol;
}

vector<int> bruteForce(const ProblemInstance &inst, int mcSamples, bool isCtg, StatusCallback cb) {
    vector<int> currentSol(inst.n_jobs);
    iota(currentSol.begin(), currentSol.end(), 0);

    vector<int> bestSol = currentSol;
    double bestCost = estimateMakespan(inst, bestSol, mcSamples, isCtg);

    reportProgress(inst, bestSol, bestCost, cb);

    while (std::next_permutation(currentSol.begin(), currentSol.end())) {
        double cost = estimateMakespan(inst, currentSol, mcSamples, isCtg);
        if (cost < bestCost) {
            bestCost = cost;
            bestSol = currentSol;
            reportProgress(inst, bestSol, bestCost, cb);
        }
    }
    return bestSol;
}

vector<int> NEH(const ProblemInstance &inst, int mcSamples, bool isCtg, StatusCallback cb) {
    vector<int> order(inst.n_jobs);
    iota(order.begin(), order.end(), 0);
    sort(order.begin(), order.end(), [&](int a, int b) {
        return estimateMakespanForJob(inst, a, mcSamples, isCtg) > estimateMakespanForJob(inst, b, mcSamples, isCtg);
    });

    vector<int> currentSol;
    for (auto &task : order) {
        int bestIndex = 0;
        double bestTime = 1e18;
        for (size_t i = 0; i <= currentSol.size(); i++) {
            vector<int> temp = currentSol;
            temp.insert(temp.begin() + i, task);
            double time = estimateMakespan(inst, temp, mcSamples, isCtg);
            if (time < bestTime) { bestTime = time; bestIndex = i; }
        }
        currentSol.insert(currentSol.begin() + bestIndex, task);
        reportProgress(inst, currentSol, estimateMakespan(inst, currentSol, mcSamples, isCtg), cb);

    }
    return currentSol;
}

extern "C" {
    void run_algorithm(
        int n_jobs, int n_machines, double* means, double* stds,
        int algo, int samples, bool is_ctg, 
        double* params,
        int* output,
        StatusCallback cb
    ) {
        ProblemInstance p;
        p.loadFromArrays(n_jobs, n_machines, means, stds);

        vector<int> result;
        if (algo == 0)      result = bruteForce(p, samples, is_ctg, cb);
        else if (algo == 1) result = simulatedAnnealing(p, samples, is_ctg, params, cb);
        else                result = NEH(p, samples, is_ctg, cb);

        for (size_t i = 0; i < result.size(); i++) output[i] = result[i] + 1;
    }
}
