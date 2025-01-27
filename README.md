# Jesse Strategy Merger
This script is used to merge multiple strategies into a single strategy. You can merge 

1) This script will take the strategies names as input.
2) Create a new strategy file strategies/MainStrategy[Y-m-d]/__init__.py
3) Find the files path will be strategies/[strategy_name]/__init__.py and get as text so that we can edit the code.

4) For each strategy
    - For every function and property not in this list: "before, after, should_long, should_short, on_open_position, on_close_position, update_position, should_cancel_entry, go_long, go_short, __init__", prefix the function by the strategy name and rename all calls to theses functions accordingly.
    - For functions should_long, should_short, copy the code add them to the new merged strategy same function name and separate them by a comment, also store the strategies that return true in an array.
    - If any of this functions return true, store the strategy name in a global variable called active_strategy.
    - For functions before, after, on_open_position, on_close_position, update_position, should_cancel_entry, go_long, go_short, __init__, copy the code add them to the new merged strategy same function name and add a condition if the active_strategy is the same as the strategy name, then execute the code.
    - For the hyperparameters, please merge all of them from each strategy into the hyperparameter function. Also prefix each parameter with the strategy name and replace all the calls in the existing code.

6) Save the new merged strategy to strategies/MainStrategy[Y-m-d]/__init__.py

# Demo
[![View video demo](https://img.youtube.com/vi/acAhmqRGwTM/0.jpg)](https://youtu.be/acAhmqRGwTM)

# Usage
```
# You can add as much strategies as you want, you are not limited to 2
python3 merge_strategies.py strategy1 strategy2 
```

# Strategy Priority
The priority of the strategies will be the same as the order you pass them in the command. In the example above strategy1 will have priority on strategy2. 

IMPORTANT NOTICE: Only 1 strategy will have an open position at a time. This means that if you combine strategies opening orders usually at the same period, it will not be effective because one will prevent the other one to trigger. The ideal technique is to create strategies with a very low "Time in market" (5-20%) that trigger at different moments in time so that this merged strategy will have an increased time in market due to the combination of them. If you add a strategy with a very high Time in market such as 80% for example, then you will prevent the other strategies to trigger.

# Note
I made this script for myself so that I can work on each strategy individually, then merge them quickly and backtest them as a group. There might be issues specific to your strategies when you merge. You can check the generated code to fix the issues. Feel free to modify and readapt this code. I hope this can help you! Cheers!
