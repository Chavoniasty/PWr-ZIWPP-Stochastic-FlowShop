#include <iostream>
#include <vector>
#include <random>

class Task {
   public:
   std::vector<float> subTask;
};

std::vector<Task> generateRandomData(int machineNum, int tasksNum) {
    float expectedValue = 4;
    float standardDeviation = 2.5;
    std::random_device rd;
    std::mt19937 generator(rd());
    std::normal_distribution<float> distribution(expectedValue, standardDeviation);

    std::vector<Task>tasks (tasksNum);
    for (int i = 0; i < tasksNum; i++) {
        for (int j = 0; j < machineNum; j++) {
            // for now its split like that instead of one-liner since its possible
            // to better contol returned value from distribution to avoid negative
            // numbers - current version depends on changing expected value and
            // standard devation to minimize number of negative values
            float newValue = distribution(generator);
            tasks[i].subTask.push_back(newValue);
        }
    }

    return tasks;
}

float calculateCost(std::vector<Task> Tasks, int machineNum) {
    std::random_device rd;
    std::mt19937 generator(rd());
    std::uniform_real_distribution<float> distribution(0.0f, 10.0f);

    return distribution(generator);
}


float getInitialTemperature(std::vector<Task> sequence) {
    std::uniform_int_distribution<> indexDist(0, sequence.size() - 1);
    std::random_device rd;
    std::mt19937 rng(rd());
    float sum = 0;

    for (int i = 0; i < 100; i++) {
        int index1 = indexDist(rng);
        int index2 = indexDist(rng);
        std::swap(sequence[index1], sequence[index2]);
        sum += calculateCost(sequence, 3);
    }
    return (-1 * (sum / 100)) / std::log(0.9);
}


std::vector<Task> anneal(std::vector<Task> solution) {
    std::uniform_real_distribution<> dist(0.0f, 1.0f);
    std::random_device rd;
    std::mt19937 rng(rd());
    std::uniform_int_distribution<> indexDist(0, solution.size() - 1);

    double probability = 0.2;
    bool acceptCondition = false;

    std::vector<Task> bestSolution = solution;
    float bestCost = calculateCost(solution, 3);
    float prevCost = calculateCost(solution, 3);

    float currentCost;
    float alpha = 0.98;
    float temperature = getInitialTemperature(solution);


    while (temperature > 0.1) {
        int index1 = indexDist(rng);
        int index2 = indexDist(rng);
        std::swap(solution[index1], solution[index2]);
        currentCost = calculateCost(solution, 3);

        if (currentCost > prevCost) {
            acceptCondition = dist(rng) >= std::exp((currentCost - prevCost) / temperature) ? true : false;
        }
        if (currentCost <= prevCost || acceptCondition) {
            prevCost = currentCost;

            if (bestCost > prevCost) {
                bestCost = prevCost;
                bestSolution = solution;
            }
        } else {
            std::cout << "swap xdd" << std::endl;
            std::swap(solution[index1], solution[index2]);
        }
        temperature *= alpha;
    }

    return bestSolution;
}



int main() {
    int machineNum = 3;

    std::vector<Task> tasks = generateRandomData(machineNum, 5);
    std::vector<Task> solution = tasks;
    anneal(solution);

    // display for debugging
    for(auto elem: tasks) {
        for (auto elemTask: elem.subTask) {
            std::cout << elemTask << " ";
        }
        std::cout << std::endl;
    }

    return 0;
}
