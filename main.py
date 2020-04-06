import numpy as np
import time
from GlobalConstants import *
from Game import *
from Environment import Environment
from MCTS import MCTS
from NeuralNet import NeuralNet
from utils import test_time
from TOPP import TOPP
from Client_side import BasicClientActor

import matplotlib.pyplot as plt

if __name__ == '__main__':
    Menu = {
        'Test': 'Testspace',
        'M': 'MCTS',
        'T': 'TOPP',
    }['M']

    if Menu == 'Testspace':
        print('Welcome to testspace')

        bca = BasicClientActor()
        bca.connect_to_server()


    elif Menu == 'MCTS':
        print('Welcome to MCTS')

        # Rounds to save parameters for ANET
        save_interval = int(np.floor(G/(num_caches-1)))
        # Only use random leaf evaluation before the first training has happened
        ane = 1
        p1_wins = 0
        p1_start = 0
        neural_net = NeuralNet(grid_size**2+1)

        # List of training-data, rbuf_size x features
        rbuf_X = np.empty((1000, input_shape), dtype=np.ndarray)
        # List of target-data
        rbuf_y = np.empty((1000, grid_size*grid_size), dtype=np.ndarray)
        # Counter for position in rbuf
        i = 0
        # Batch size for training
        batch_size = 64
        # Flag indicating if the neural net should train
        train = False

        # Save model before training
        neural_net.save_params(0)
        for j in range(G):
            env = Environment(grid_size)
            mcts = MCTS(env, neural_net, ane)
            print('...using {}% ANET evaluation'.format(
                np.round((1-ane)*100, 3)))
            states_in_game = []
            state = env.generate_initial_state()
            states_in_game.append(state)
            # Initiate starting player for each game (should always be 1)
            player_number = P
            # Player add 1 if player_number is 1 (P1 starts)
            p1_start += player_number + 1 and 1
            while not env.check_game_done(state):
                possible_actions = env.get_possible_actions_from_state(state)
                # Do M simulations
                best_action, D = mcts.simulate(player_number, M, state)

                # Add tuple of training example-data and target to RBUF
                features = np.append(
                    state, player_number)
                rbuf_X[i % 1000] = features
                rbuf_y[i % 1000] = D
                # Increase counter
                i += 1

                # Do the action, get next state
                state = env.generate_child_state_from_action(
                    state, best_action, player_number, verbose)
                states_in_game.append(state)
                # Next players turn
                player_number ^= (p1 ^ p2)
            # Winner was the last player to make a move (one before player_number)
            winner = player_number ^ (p1 ^ p2)
            print('Player {} wins'.format(winner))
            if winner == 1:
                p1_wins += 1
            print('*** Game {} done ***'.format(j+1))
            if visualize:
                env.visualize(states_in_game, 500)


            # Do not train until the rbuf has filled up to batch size
            # After the rbuf has filled to batch size the first time, train after every game
            if i >= batch_size and train == False:
                # Turn on leaf evaluation with anet (one time)
                print('...evaluating leaf nodes with ANET')
                ane = random_leaf_eval_fraction
                # Turn on training of anet
                print(
                    '...turning on training, there are now {} examples to train on'.format(i))
                train = True


            # Train the neural net
            if train:
                filled_rows_lenght = rbuf_X[(rbuf_X != np.array(None)).any(axis=1)].shape[0]
                random_rows = np.random.choice(filled_rows_lenght, batch_size, replace=False)
                # Get the same rows from X and y
                train_X = rbuf_X[random_rows].astype(float)
                train_y = rbuf_y[random_rows].astype(float)
                neural_net.train_on_rbuf(train_X, train_y, batch_size)
                # Decay anet_fraction
                ane *= random_leaf_eval_decay

            # j begins at 0, so add 1
            if (j+1) % save_interval == 0:
                neural_net.save_params('grid_size_{}_game_{}'.format(grid_size, (j+1)))

        print('Player 1 wins {} of {} games ({}%).\nPlayer 1 started {}% of the time'.format(
            p1_wins, G, p1_wins/G*100, p1_start/G*100))

    elif Menu == 'TOPP':
        print('******* WELCOME TO THE TOURNAMENT *******')

        agents=[]

        # NOTE: i: adam, lr = 0.001, 20 epochs
        # NOTE: i*10: adam, lr = 0.001, 50 epochs
        a=NeuralNet()
        a.load_params('./NoNN/save_{}'.format(0))
        a.anet._name='ANET_'+str(0)
        agents.append(a)
        for i in [70, 140, 210]:  # np.linspace(0, G, num_caches, dtype=int):
            print('...fetching agent ', i)
            a=NeuralNet()
            a.load_params('./NoNN/save_grid_size_3_game_{}'.format(i))
            a.anet._name='ANET_'+str(i)
            agents.append(a)

        topp=TOPP(agents)
        topp.tournament()

        """
        TODO:
        - DONE: Run games project 2-style - requires clean GCs, working env
        - DONE: Add NN to rollouts (ANET)
        - Add target policy update after each actual game (train NN)
        - Make list of architectual choices to try and train the network on
            - Send as input to NN, not from GC (just when testing this, use GC else)
            - Save each M trained anets with different names for different architectures
            - Decide how to measure success
            - Save success-measurement with each agent
            - Run small test to ensure it works
            - Run large test overnight: 5x5 board, 4 ANETS, minimum 200 episodes (Try 1000 simulations)
            - Log all results
            - Choose one architecture

        # NOTE: questions
        - time: batch size of 64 or 32, fyll opp fra starten i rbuf, tren etter hvert spill
        - anets are insecure to begin with (too large search-space to simulate to the end), but get more secure
            as the game gets closer to an end
        - ALTERNATE STARTING PLAYER WHEN PLAYING GAMES TO TRAIN ANETS?
        """
