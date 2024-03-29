import numpy as np
from Node import Node
import random
from GlobalConstants import grid_size, p1, p2

class MCTS:
    def __init__(self, env, neural_net, random_leaf_eval_fraction):
        self.c = 1
        # Dict to keep different values for nodes
        self.states = {}
        self.sim_env = env
        self.neural_net = neural_net
        self.random_leaf_eval_fraction = random_leaf_eval_fraction

    def simulate(self, player_number: tuple, M: int, init_state):
        # Create a node from begin-state
        # NOTE: Everything is reset each round
        node = Node(init_state, parent=None, is_final=False, is_root=True)
        for i in range(M):
            self.p_num = player_number
            # 1. Follow tree policy to leaf node
            # Note: leaf-node may be a final state, but not necessary
            leaf_node = self.traverse_tree(node)

            # 2. When leaf-node is found, expand the leaf to get all children and return one of them (or `node` if it is a final state)
            leaf_node = self.expand_leaf_node(leaf_node)

            # 3. Leaf evaluation
            if random.random() <= self.random_leaf_eval_fraction:
                # Use random leaf_eval
                self.rollout_evaluation = self.default_policy
            else:
                # Use ANETs leaf_eval
                self.rollout_evaluation = self.neural_net.default_policy
            eval_value = self.evaluate_leaf(leaf_node)

            # 4. Backprop
            self.backpropagate(leaf_node, eval_value)
            #input('...press any key to do next simulation\n\n')
        action_distributions = self.get_action_distribution(node)
        return self.get_simulated_action(node, player_number), action_distributions

    def get_action_distribution(self, node):
        # Returns normalized action distribution
        action_distributions = np.zeros(len(node.name))
        # For all possible actions, add corresponding number of times action has been taken
        np.put(action_distributions, list(node.N_sa.keys()), list(node.N_sa.values()))
        # Normalize
        action_distributions /= np.sum(action_distributions)
        return action_distributions


    def tree_policy(self, node, combine_function, arg_function, best_value):
        # Using UCT to find best action in the tree
        # :returns: index of best action in nodes actions
        # inout: node, possible actions from state,arg_function is either max or min, combine_function is either sum or minus
        best_action_index = None
        for i, a in enumerate(node.actions):
            u = self.c*np.sqrt(np.log(node.N_s)/(1+node.N_sa[a]))
            action_value = node.Q_sa[a]
            possible_best = combine_function(action_value, u)
            best_value = arg_function(possible_best, best_value)
            if best_value == possible_best:
                best_action_index = i
        return best_action_index

    def traverse_tree(self, root_node):
        # Returns leafnode
        node = root_node
        # Traverse until node is a leaf-node or a final state
        while not (node.is_leaf or node.is_final_state):
            combine_func, arg_func, best_value = self.get_minimax_functions(
                self.p_num)
            action_index = self.tree_policy(
                node, combine_func, arg_func, best_value)
            # Set chosen action for traversing later
            node.set_action_done(node.actions[action_index])
            # Get child-node with same index as best action
            node = node.children[action_index]
            # Next players turn
            self.p_num = self.p_num ^ (p1 ^ p2)
        return node

    def expand_leaf_node(self, node):
        # Expand if the node is not a final state
        if not node.is_final_state:
            # Get all action from node, and the resulting states
            edges = self.sim_env.get_possible_actions_from_state(node.name)
            child_nodes = []
            for e in edges:
                # Get the child state action `e` would result in
                child_state = self.sim_env.generate_child_state_from_action(
                    node.name, e, self.p_num)
                is_final = self.sim_env.check_game_done(child_state)
                # Add child node, with parent `node`
                child_node = Node(child_state, parent=node, is_final=is_final)
                child_nodes.append(child_node)
            # Add all children and actions for node
            node.set_children(edges, child_nodes)
            # Moving on to a new layer, so next players turn
            self.p_num = self.p_num ^ (p1 ^ p2)
            # Set action_done to the last action, as the last child is returned
            node.set_action_done(edges[-1])
            # Returning last child node, as the value of all child_nodes as unknown
            return child_node
        else:
            # Node is a leaf-node already (final state), so return it
            return node

    def default_policy(self, possible_actions, state, p_num):
        # Using uniform distribution to get an action
        # All parameters except `possible_actions` are dummy-parameters, to match ANETs parameters
        random_index = np.random.randint(len(possible_actions))
        return possible_actions[random_index]

    def evaluate_leaf(self, node):
        # Do rollout on `node` to get value
        state = node.name
        while not self.sim_env.check_game_done(state):
            possible_actions = self.sim_env.get_possible_actions_from_state(
                state)
            action = self.rollout_evaluation(possible_actions, state, self.p_num)
            state = self.sim_env.generate_child_state_from_action(
                state, action, self.p_num)
            self.p_num = self.p_num ^ (p1 ^ p2)
        # Player that did last move is the final player
        final_player = self.p_num ^ (p1 ^ p2)
        eval_value = self.sim_env.get_environment_value(final_player)
        return eval_value

    def get_simulated_action(self, root_node, player_num):
        """
        :param root_node: Node, represents state to find best action from
        :param player_num: tuple(1,0) for P1, (0,1) for P2

        :returns: best action for the player from the current state, given by the highest Q(s,a)-value
        """
        best_sim_action = None
        _, arg_func, best_value = self.get_minimax_functions(player_num)
        for a in root_node.actions:
            poss_best_value = root_node.Q_sa[a]
            best_value = arg_func(best_value, root_node.Q_sa[a])
            if poss_best_value == best_value:
                best_value = poss_best_value
                best_sim_action = a
        return best_sim_action

    def backpropagate(self, node, eval_value):
        # BP until node has no parent
        while not node.is_root:
            # Skip leaf node, as it has no N(s,a) values
            node = node.parent
            node.update(eval_value)

    def get_minimax_functions(self, p_num):
        if p_num == 1:
            return lambda x1, x2: x1+x2, lambda x1, x2: np.max((x1, x2)), float("-inf")
        elif p_num == -1:
            return lambda x1, x2: x1-x2, lambda x1, x2: np.min((x1, x2)), float("inf")
        else:
            raise ValueError('Invalid player number: {}'.format(p_num))
