import pandas as pd
import numpy as np
import plotly.express as pe
import plotly.io as pio
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import sklearn


# all functions are inside their own script to make this script cleaner
from utils import connect_to_db, run_query, convert_data_type_names, clean_query

from download_data import generate_download_links

# Define location of the db
db_dir = 'db.sqlite'
# Define the name of the table to hold the data
table_name = 'results'

result = run_query(query=f'select * from {table_name}', return_data=True, path_to_db=db_dir)

cols = ['fthg', 'ftag', 'hthg',
       'htag',  'home_shots', 'away_shots', 'hst', 'ast',
       'hf', 'af', 'hc', 'ac', 'hy', 'ay', 'hr', 'ar']
result.loc[result['season'] == '1415', cols] = result.loc[result['season'] == '1415', cols]/10

result.groupby('season').mean()


# Does Home Advantage play a part in winning the game?
# Percent of times the home team wins compared to draw and away win
percent_of_home_wins = len(result[result["ftr"] == "H"]) / len(result)  # Show bool of if ftr is H
percent_of_home_draws = len(result[result["ftr"] == "D"]) / len(result)  # Show bool of if ftr is D
percent_of_home_loss = len(result[result["ftr"] == "A"]) / len(result)  # Show bool of if ftr is A
assert np.round(percent_of_home_wins + percent_of_home_draws + percent_of_home_loss) == 1, ""
# Check percentage includes 100% games

# Get percent of Full Time wins for Home Teams
percent_of_home_wins = len(result[result["ftr"] == "H"]) / len(result)  # Show bool of if ftr is H
print(percent_of_home_wins)
# Get percent of Half Time Leads for Home Teams
percent_of_halftime_lead_h = len(result[result["htr"] == "H"]) / len(result)
percent_of_halftime_lead_d = len(result[result["htr"] == "D"]) / len(result)
percent_of_halftime_lead_a = len(result[result["htr"] == "A"]) / len(result)

# Is Team Form a good predictor of whether the team will win their next game?
# Team Form based on the Home Goals in previous 5 games
result.groupby("hometeam").fthg.rolling(
    5, min_periods=5, center=False, win_type=None, on=None, axis=0, closed=None).mean()
# This is okay, but I want overall form
# I need one row per team per game to find the Home Form value
result["id"] = result.index
homecols = ["id", "date", "hometeam", "fthg", "ftag", "hc", "ac", "hf", "af", "hy", "ay", "hr", "ar", "season"]
homecolsnew = ["id", "date", "team", "goalsfor", "goalsagainst", "cornersfor", "cornersagainst", "foulsfor",
               "foulsagainst", "yellowfor", "yellowagainst", "redfor", "redagainst", "season"]
df_home = result[homecols]
df_home.columns=homecolsnew
df_home.loc[:, "ishome"] = True

# Team Form based on the Away Goals in previous 5 games
awaycols = ["id", "date", "awayteam", "ftag", "fthg", "ac", "hc", "af", "hf", "ay", "hy", "hr", "ar", "season"]
awaycolsnew = ["id", "date", "team", "goalsfor", "goalsagainst", "cornersfor", "cornersagainst", "foulsfor",
               "foulsagainst", "yellowfor", "yellowagainst", "redagainst", "redfor", "season"]
df_away = result[awaycols]
df_away.columns=awaycolsnew
df_away.loc[:, "ishome"] = False

# Split home and away teams into individual rows
teamform = df_home
teamform = teamform.append(df_away)
teamform = teamform.sort_values('id')
assert len(teamform) == len(result) * 2  # Testing new dataframe is the correct size


# Make a rolling average window for features
# Team Form for past 5 games (excluding most recent game)
# Lag goals for, so we don't generate features from the game we are trying to predict



def get_result(x):
    if x['goalsfor'] > x['goalsagainst']:
        return "W"
    elif x['goalsfor'] < x['goalsagainst']:
        return "L"
    else:
        return "D"


# Applies the 'get_result' function to every row in teamform, adds results to a new col called "result"


teamform['result'] = teamform.apply(get_result, axis=1)

# Team Form : Add columns
teamform['won'] = teamform['result'] == 'W'  # Adds "won" col to teamform df stating if team won
teamform['lost'] = teamform['result'] == 'L'  # Adds "lost" col to teamform stating if team lost

win_rates = teamform.groupby(['team', 'season']).won.mean().reset_index()  # The win rate of all teams
win_rates.columns = ['team', 'season', 'win_rate']
teamform = pd.merge(teamform, win_rates, on=['team', 'season'])
teamform['won'] = teamform['win_rate']

loss_rates = teamform.groupby(['team', 'season']).lost.mean().reset_index()  # The win rate of all teams
loss_rates.columns = ['team', 'season', 'loss_rate']
teamform = pd.merge(teamform, loss_rates, on=['team', 'season'])
teamform['lost'] = teamform['loss_rate']

def add_rolling_average(df, column='goalsfor', window=5, min_periods=5):
    # Shift so I dont use the current game score as part of the average
    df[f'{column}_lagged'] = df.groupby('team')[column].shift(1)
    test = df.groupby("team")[f"{column}_lagged"].rolling(window, min_periods).mean().reset_index()
    test.columns = ['team', 'index', f"{column}_l{window}"]
    df['index'] = df.index.copy()
    df = pd.merge(df, test, how='left', on=['team', 'index'])
    df.drop(f'{column}_lagged', axis=1, inplace=True)
    return df


teamform = add_rolling_average(teamform, column='goalsfor', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='goalsagainst', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='cornersfor', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='cornersagainst', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='foulsfor', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='foulsagainst', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='yellowfor', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='yellowagainst', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='redfor', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='redagainst', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='won', window=5, min_periods=5)
teamform = add_rolling_average(teamform, column='lost', window=5, min_periods=5)


# Calculate the Attacking and Defending strength of each team
# Get average goals from last 5 games to determine attacking strength
# Use Pandas Rank to decide the rank and remove human bias
# Compute numerical data ranks (1 through n) along axis
# Create a Ranking function that I can reuse on different columns

def ranking_function(teamform, col_name, new_col_name, ascending=True):

    teamform['pct_rank'] = teamform[col_name].shift(1).rank(ascending=ascending, pct=True)

    # Now I need to create the column "attacking_strength_l5" in team form
    # Create a list of conditions
    conditions = [
        (teamform['pct_rank'] <= 0.33),
        (teamform['pct_rank'] >= 0.66),
        (teamform['pct_rank'] > 0.33) & (teamform['pct_rank'] < 0.66)
    ]

    # Create a list of values we want to assign for each condition
    attack_form_values = ["low", "high", "medium"]

    # Create a new column and use np.select to assign values
    teamform[new_col_name] = np.select(conditions, attack_form_values)
    return teamform


teamform = ranking_function(teamform, "goalsfor", "attacking_strength_l5" )
teamform = ranking_function(teamform, "goalsagainst", "defensive_strength_l5", ascending=False)


teamform['pct_rank'] = teamform['goalsfor_l5'].rank(pct=True)

# Now I need to create the column "attacking_strength_l5" in team form
# Create a list of conditions
conditions = [
    (teamform['pct_rank'] <= 0.33),
    (teamform['pct_rank'] >= 0.66),
    (teamform['pct_rank'] > 0.33) & (teamform['pct_rank'] < 0.66)
     ]

# Create a list of values we want to assign for each condition
attack_form_values = ["low", "high", "medium"]

# Create a new column and use np.select to assign values
teamform["attacking_strength_l5"] = np.select(conditions, attack_form_values)

# Display updated DataFrame
teamform.head()

# Add a Column to check whether the team won or not
# First define the get_result function


# teamform['result'] = teamform.apply(lambda x: get_result(x), axis=1)



# VISUALISATION

pio.renderers.default = 'browser'

# Plot goals for each match for home team
import plotly
home_teams = teamform[teamform['ishome']==True]
away_teams = teamform[teamform['ishome']==False]
home_goals = pe.histogram(home_teams, x='goalsfor', title='Goals scored by home team (histogram)')
plotly.offline.plot(home_goals)
away_goals = pe.histogram(away_teams, x='goalsfor', title='Goals scored by away team (histogram)')
plotly.offline.plot(away_goals)

# Team Summary : Add columns
# team_summary = teamform.groupby(['team', 'season'])['won', 'lost', 'goalsfor', 'goalsagainst',
#                                                    'goalsfor_l5', 'goalsagainst_l5', 'cornersfor_l5',
#                                                    'cornersagainst_l5', 'foulsfor_l5', 'foulsagainst_l5',
#                                                    'yellowfor_l5', 'yellowagainst_l5', 'redfor_l5', 'redagainst_l5'].mean().reset_index()
# team_summary.corr() # This gives me a correlation matrix. Easy way to visualise data.


# Scatter plot: Goals for vs win rate
plot_goalsFor = pe.scatter(teamform, x='won_l5', y='goalsfor_l5', labels='season', color='team', title='Goals for vs win rate')
plotly.offline.plot(plot_goalsFor)
# plot_goalsFor.show()
# This shows a positive correlation suggesting a better attacking strength based on form may equate to a higher win rate
# This would make a good feature.

# Scatter plot: Goals against vs win rate
plot_goalsAgainst = pe.scatter(teamform, x='won_l5', y='goalsagainst_l5', labels='season', color='team', title='Goals Against vs win rate')
plotly.offline.plot(plot_goalsAgainst)
# Bar Chart: Goals Against vs win rate


# Scatter plot: Corners for vs win rate
plot_CornersFor = pe.scatter(teamform, x='won_l5', y='cornersfor_l5', labels='season', color='team', title='Corners for vs win rate')
plotly.offline.plot(plot_CornersFor)
# Bar Chart: Corners for vs win rate
# bar_CornersFor = pe.bar(teamform, x='won_l5', y='cornersfor_l5', labels='season', color='team', title='Corners for vs win rate')
# plotly.offline.plot(bar_CornersFor)


# Scatter plot: Corners against vs win rate
plot_CornersAgainst = pe.scatter(teamform, x='won_l5', y='cornersagainst_l5', labels='season', color='team', title='Corners against vs win rate')
plotly.offline.plot(plot_CornersAgainst)
# Bar Chart: Corners against vs win rate
# bar_CornersAgainst = pe.bar(teamform, x='won_l5', y='cornersagainst_l5', labels='season', color='team', title='Corners against vs win rate')
# plotly.offline.plot(bar_CornersAgainst)


# Scatter plot: Fouls committed vs win rate
plot_FoulsFor = pe.scatter(teamform, x='won_l5', y='foulsfor_l5', labels='season', color='team', title='Fouls for vs win rate')
plotly.offline.plot(plot_FoulsFor)
# Bar Chart: Fouls committed vs win rate
# bar_FoulsFor = pe.bar(teamform, x='won_l5', y='foulsfor_l5', labels='season', color='team', title='Fouls for vs win rate')
# plotly.offline.plot(bar_FoulsFor)


# Scatter plot: Fouls against vs win rate

# Bar Chart: Fouls against vs win rate
# bar_FoulsAgainst = pe.bar(teamform, x='won_l5', y='foulsagainst_l5', labels='season', color='team', title='Fouls against vs win rate')
# plotly.offline.plot(bar_FoulsAgainst)

# Scatter plot: Yellow cards for vs win rate
plot_YellowFor = pe.scatter(teamform, x='won_l5', y='yellowfor_l5', labels='season', color='team', title='Yellow card for vs win rate')
plotly.offline.plot(plot_YellowFor)
# Bar Chart: Yellow cards for vs win rate
# bar_YellowFor = pe.bar(teamform, x='won_l5', y='yellowfor_l5', labels='season', color='team', title='Yellow card for vs win rate')
# plotly.offline.plot(bar_YellowFor)

# Scatter plot: Yellow cards against vs win rate
plot_YellowAgainst = pe.scatter(teamform, x='won_l5', y='yellowagainst_l5', labels='season', color='team', title='Yellow card against vs win rate')
plotly.offline.plot(plot_YellowAgainst)
# Bar Chart: Yellow cards against vs win rate
# bar_YellowAgainst = pe.bar(teamform, x='won_l5', y='yellowagainst_l5', labels='season', color='team', title='Yellow card against vs win rate')
# plotly.offline.plot(bar_YellowAgainst)


# Scatter plot: Red card for vs win rate
plot_RedFor = pe.scatter(teamform, x='won_l5', y='redfor_l5', labels='season', color='team', title='Red card for vs win rate')
plotly.offline.plot(plot_RedFor)
# Bar Chart: Red card for vs win rate
# bar_RedFor = pe.bar(teamform, x='won_l5', y='redfor_l5', labels='season', color='team', title='Red card for vs win rate')
# plotly.offline.plot(bar_RedFor)


# Scatter plot: Red card against vs win rate
plot_RedAgainst = pe.scatter(teamform, x='won_l5', y='redagainst_l5', labels='season', color='team', title='Red card against vs win rate')
plotly.offline.plot(plot_RedAgainst)
# Bar Chart: Red card against vs win rate
# bar_RedAgainst = pe.bar(teamform, x='won_l5', y='redagainst_l5', labels='season', color='team', title='Red card against vs win rate')
# plotly.offline.plot(bar_RedAgainst)


# Bar Chart showing how each feature correlates to each other
cor = teamform.corr()['won']
fig = pe.bar(cor)
plotly.offline.plot(fig)


# Join home and away features onto a single row - this is so we don't use only half of the data for predictions
full_teams = pd.merge(home_teams, away_teams, on=['id', 'date']).reset_index(drop=True)

# Evaluation metric - Accuracy, because the classes (H/D/A) are fairly balanced
def assign_result(x):
    if x == 'W':
        return 'H'
    elif x == 'L':
        return 'A'
    else:
        return 'D'

# Add a column for result that is home, draw or away
for i in range(len(full_teams)):
    full_teams.loc[i, 'final_result'] = assign_result(full_teams.loc[i, 'result_x'])


# MODEL BUILDING
# Ensure categorical columns are one-hot encoded (they are either 0 or 1, and don't contain strings"
# I do this because models do not handle string categories

categorical_cols = ['attacking_strength_l5_x', 'defensive_strength_l5_x',
                    'attacking_strength_l5_y', 'defensive_strength_l5_y']
categorical_dummies = pd.get_dummies(full_teams[categorical_cols])
# Add these one-hot encoded columns to the data
full_teams = pd.concat([full_teams.reset_index(drop=True), categorical_dummies.reset_index(drop=True)], axis=1)
# Drop the original columns
full_teams = full_teams.drop(categorical_cols, axis=1)
# Redefine features with the new columns
features = [
   # Home team features
   'goalsfor_l5_x', 'cornersfor_l5_x', 'foulsagainst_l5_x',
   # Away team features
   'goalsagainst_l5_y', 'cornersagainst_l5_y', 'foulsfor_l5_y'
] + list(categorical_dummies.columns)

# Remove null values as  the model cant handle them
full_teams = full_teams.dropna()

# Drop null values as the model cant deal with NULLs
X = full_teams[features]
y = full_teams['final_result']

# Scale the data
scaler = sklearn.preprocessing.StandardScaler()
full_teams[features] = scaler.fit_transform(full_teams[features])

# Split data into test and train
X_train, X_test, y_train, y_test = train_test_split(full_teams[features], full_teams['final_result'])

# Create a random forest classifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score

# Models to test
# Linear model
# Random forest
# XGBoost

# Train each model, evaluate it on a test set, using balanced_accuracy_score

def train_evaluate_model(model, X_train, X_test, y_train, y_test):
    # Fit a model to the data
    model.fit(X_train, y_train)
    # Generate new predictions
    preds = model.predict(X_test)
    # Evaluate model in terms of accuracy
    performance = accuracy_score(y_test, preds)
    return {"model": model, "performance": performance}


# Create candidate models to test
svc_classifier = SVC()
rf_classifier = RandomForestClassifier()
xgb_classifier = XGBClassifier()

model_performance = {}

for model in [('support_vector_machine', svc_classifier), ('random_forest', rf_classifier), ('xgboost', xgb_classifier)]:
    print(f"training {model}")
    model_performance[model[0]] = train_evaluate_model(model[1], X_train, X_test, y_train, y_test)
    print(f"Model performance: {model_performance[model[0]]['performance']}")

# TODO: Compare the performance of each model and see which is the best

# Creating a baseline
# Baseline performance is set to the performance given for if we picked home team to win every time
baseline_performance = accuracy_score(y_test, ['H']*len(y_test))

# Using model_performance_against_baseline to compare the model performance to the baseline
performance_vs_baseline = model_performance['support_vector_machine']['performance']/baseline_performance-1
# This tells you how much better the model is than the baseline as a %
print(f"The SVM model beats the baseline by {round(performance_vs_baseline, 4)}%")
performance_vs_baseline = model_performance['random_forest']['performance']/baseline_performance-1
# This tells you how much better the model is than the baseline as a %
print(f"The RandomForest model beats the baseline by {round(performance_vs_baseline, 4)}%")
performance_vs_baseline = model_performance['xgboost']['performance']/baseline_performance-1
# This tells you how much better the model is than the baseline as a %
print(f"The XGBOOST model beats the baseline by {round(performance_vs_baseline, 4)}%")