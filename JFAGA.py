import random
import argparse
from deap import base
from deap import creator
from deap import tools
from scoop import futures
import SampleSimulator as Sim
import JFAFeatures as jf
import ProblemGenerators as pg
import copy
import time


def jfa_remove_inaccessible_actions(problem, actions):
    cleaned_list = []
    env = Sim.Simulation(Sim.state_to_dict)
    state = copy.deepcopy(problem)
    achieved_reward = 0
    for action in actions:
        try:
            state, reward, terminal = env.update_state(action, state)
            cleaned_list.append(action)
        except IndexError:  # This means that the action was not selectable, but there are still available actions.
            #  print(f"Error taking action {opportunities[chromosome[opportunity]]}")
            continue
        achieved_reward += reward
        if terminal:
            break
    return achieved_reward,


def jfa_ga_solver(problem, population_size=40, crossover_probability=0.5, mutation_probability=0.25,
                  generations_qty=200, tournament_fraction=5, mutation_fraction=10):
    rewards, times, actions = jfa_ga_explorer(problem, population_size, generations_qty, crossover_probability,
                                              mutation_probability, tournament_fraction, mutation_fraction)
    total_reward = sum(problem['Targets'][:, jf.TaskFeatures.VALUE])
    return total_reward - rewards[-1], actions[-1]


def jfa_ga_explorer(problem, population_size=40, generations_qty=5000, crossover_probability=0.7,
                    mutation_probability=0.25, tournament_fraction=5, mutation_fraction=10):
    times = []
    rewards = []
    actions = []

    max_hits = 2
    env = Sim.Simulation(Sim.state_to_dict)
    num_effectors = len(problem['Effectors'])
    num_targets = len(problem['Targets'])
    opportunities = []
    for eff_index in range(num_effectors):
        for tar_index in range(num_targets):
            if problem['Opportunities'][eff_index][tar_index][jf.OpportunityFeatures.SELECTABLE]:
                for _ in range(max_hits):
                    opportunities.append((eff_index, tar_index))
    num_opportunities = len(opportunities)

    def evaluate_with_indices(chromosome):
        state = copy.deepcopy(problem)
        achieved_reward = 0
        terminal = False
        for opportunity in chromosome:
            try:
                state, reward, terminal = env.update_state(opportunities[chromosome[opportunity]], state)
            except IndexError:  # This means that the action was not selectable, but there are still available actions.
                #  print(f"Error taking action {opportunities[chromosome[opportunity]]}")
                continue
            achieved_reward += reward
            if terminal:
                break
        if not terminal:
            print(f"Error: opportunities exhausted and have not reached a terminal state")
        return achieved_reward,

    history = tools.History()
    hall_of_fame = tools.HallOfFame(1)
    if hasattr(creator, "FitnessMax"):  # deap doesn't like it when you recreate Creator methods.
        del creator.FitnessMax
    if hasattr(creator, "Individual"):
        del creator.Individual
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMax)

    toolbox = base.Toolbox()
    toolbox.register("attr_indices", random.sample, range(num_opportunities), num_opportunities)
    toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.attr_indices)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("evaluate", evaluate_with_indices)
    toolbox.register("mate", tools.cxPartialyMatched)  # IEEE paper says PMX is better than OX

    toolbox.register("mutate", tools.mutShuffleIndexes, indpb=1 // mutation_fraction)
    toolbox.register("select", tools.selRoulette)
    #  toolbox.register("map", futures.map)

    population = toolbox.population(n=population_size)
    history.update(population)
    fitnesses = map(toolbox.evaluate, population)

    for individual, fitness in zip(population, fitnesses):
        individual.fitness.values = fitness

    start_time = time.time()

    for g in range(generations_qty):
        offspring = toolbox.select(population, len(population))
        offspring = list(map(toolbox.clone, offspring))

        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < crossover_probability:
                toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values

        for mutant in offspring:
            if random.random() < mutation_probability:
                toolbox.mutate(mutant)
                del mutant.fitness.values

        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalid_ind)
        for individual, fitness in zip(invalid_ind, fitnesses):
            individual.fitness.values = fitness
        population[:] = offspring
        hall_of_fame.update(population)
        if not g % 10:
            times.append(time.time() - start_time)
            rewards.append(hall_of_fame[0].fitness.values[0])
            clean_actions = False
            if clean_actions:
                best_actions = jfa_remove_inaccessible_actions(problem, [opportunities[i] for i in hall_of_fame[0]])
            else:
                best_actions = [opportunities[i] for i in hall_of_fame[0]]
            actions.append(best_actions)
        if not g % 20:
            print(f"Generation: {g}")

    return rewards, times, actions


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--problem', type=str, help="The filename of the problem json you would like to load",
                        default='4x10\\GVeCUHSIRJGfhz0lHlwcvw.json')
    parser.add_argument('--population', type=int, help="The size of the population for each generation", default=80)
    parser.add_argument('--generations', type=int, help="The number of generations to evaluate for", default=200)
    args = parser.parse_args()

    scenario = pg.loadProblem(args.problem)
    result = jfa_ga_solver(scenario, population_size=args.population, generations_qty=args.generations)
    print(result)