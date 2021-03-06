#!/usr/bin/env python
# coding: utf-8

# # QSAR for anti-malaria drugs
 
'''Dataset was obtained from Chembl database. 
The project will search for the best QSAR models as a relationship 
between the input features and the output class (anti-malaria or not). 
The model input features are obtained as moving averages (MAs) 
of the original Chembl drug features in specific experimental conditions. 
The current dataset has already the final MA descriptors. 
The dataset was cleaned for duplicate rows and the rows where shuffled.'''


# Input specific libraries for the calculations:

#get_ipython().run_line_magic('reload_ext', 'autoreload')
#get_ipython().run_line_magic('autoreload', '2')
#get_ipython().run_line_magic('matplotlib', 'inline')

# Remove warnings
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


import numpy as np
import pandas as pd
import time
import matplotlib.pyplot as plt

from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, GridSearchCV, StratifiedKFold, train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score,f1_score, recall_score, precision_score
from sklearn.metrics import confusion_matrix, classification_report
from sklearn.utils import class_weight, shuffle

from sklearn.naive_bayes import GaussianNB
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression, LassoCV
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.ensemble import GradientBoostingClassifier, BaggingClassifier, AdaBoostClassifier
#from xgboost import XGBClassifier
from sklearn.svm import SVC
from sklearn.gaussian_process.kernels import RBF
from sklearn.svm import LinearSVC

from sklearn.decomposition import PCA
from sklearn.preprocessing import MinMaxScaler
from sklearn.feature_selection import RFECV, VarianceThreshold, SelectKBest, chi2
from sklearn.feature_selection import SelectFromModel, SelectPercentile, f_classif


# Define few global variables (name of class column, the seed for random generator):
outVar = 'Class'
seed = 42  # To ensure that it is always the same split
np.random.seed(seed)

# Read dataset from datasets folder as CSV:
sFile = '.\datasets\ds.'+str(outVar)+'.csv'
print('\n-> Read dataset', sFile)
df = pd.read_csv(sFile)  # To read as DataFrame (data and header)
print('* Columns:',list(df.columns))  # Print the names of the columns to verify
print('* Dimension:', df.shape)

# Split dataset into 80% train and 20% test subsets using class stratification:
X_data = df.drop(outVar, axis=1).values  # Remove the output and we are left with the columns of features (array)
Y_data = df[outVar].values 
X_tr, X_ts, y_tr, y_ts = train_test_split(X_data, Y_data,
                                          random_state=seed, test_size=0.20,
                                          stratify=Y_data)  # To take into account the proportion of classes in each split
print("Dimensions for splits:\n", 'X_tr.shape =', X_tr.shape, 'X_ts.shape =', X_ts.shape,
      'y_tr.shape =', y_tr.shape, 'y_ts.shape =', y_ts.shape)

# Normalize dataset with values between 0 and 1:
'''Because the probability feature is already between 0 and 1, we used the same normalization range for all the features. 
The normalization used only the training values and it was applied to the test subset.'''
scaler = MinMaxScaler()
X_tr_norm = scaler.fit_transform(X_tr)
X_ts_norm = scaler.transform(X_ts)

# Save train subset as file:
df_tr_norm = pd.DataFrame(X_tr_norm, columns = list(df.columns)[:-1])
df_tr_norm['Class'] = y_tr
df_tr_norm.shape
df_tr_norm.to_csv(r'datasets\ds.Class.tr.norm.csv',index=False)  # Have to change the route. Index false to doesn't put an index column.

# Save test subset as file:
df_ts_norm = pd.DataFrame(X_ts_norm, columns = list(df.columns)[:-1])
df_ts_norm['Class'] = y_ts
df_ts_norm.shape
df_ts_norm.to_csv(r'datasets\ds.Class.ts.norm.csv',index=False)


# ### ML with training and test subsets
# 
# Read train and test subsets as dataframes:
df_tr_norm = pd.read_csv(r'datasets\ds.Class.tr.norm.csv')
df_ts_norm = pd.read_csv(r'datasets\ds.Class.ts.norm.csv')
print('Training shape:',df_tr_norm.shape)
print('Test shape:',df_ts_norm.shape)

# Get data only:
X_tr_norm = df_tr_norm.drop(outVar, axis=1).values
y_tr_norm = df_tr_norm[outVar].values
X_ts_norm = df_ts_norm.drop(outVar, axis=1).values
y_ts_norm = df_ts_norm[outVar].values


# Define a function for ML with a single method and statistics 
# such as ACC, AUROC, precision, recall, f1score:
def ML_baseline(cls, X_tr, y_tr, X_ts, y_ts, seed=42, classes=['0','1']):
    ACC = 0
    AUROC = 0
    precision = 0 
    recall = 0
    f1score = 0
    
    cls_name = type(cls).__name__
    
    start_time = time.time()
    cls.fit(X_tr, y_tr)
    print('>', cls_name, "training: %0.2f mins " % ((time.time() - start_time)/60))
    
    # predictions
    y_pred  = cls.predict(X_ts)
    y_probs = cls.predict_proba(X_ts)[:, 1]
    cls_rep = classification_report(y_ts, y_pred, target_names=classes,
                                    output_dict=True, digits=3)
    print(cls_rep)
    
    ACC       = accuracy_score(y_ts, y_pred)
    AUROC     = roc_auc_score(y_ts, y_probs)
    precision = cls_rep['weighted avg']['precision']
    recall    = cls_rep['weighted avg']['recall']
    f1score   = cls_rep['weighted avg']['f1-score']  
    
    return ACC, AUROC, precision, recall, f1score

# Define a function to return a dictionary with the class ballance:
def  set_weights(y_data, option='balanced'):
    """Estimate class weights for umbalanced dataset
       If ‘balanced’, class weights will be given by n_samples / (n_classes * np.bincount(y)). 
       If a dictionary is given, keys are classes and values are corresponding class weights. 
       If None is given, the class weights will be uniform """
    cw = class_weight.compute_class_weight(option, np.unique(y_data), y_data)
    w = {i:j for i,j in zip(np.unique(y_data), cw)}
    return w

class_weights = set_weights(list(y_tr_norm), option='balanced')
print('* Class ballance in training set:', class_weights)


# Define the list of classifiers for our ML baseline:
# priors for LDA
priors = [(class_weights[0]/(class_weights[0]+class_weights[1])), 
          (class_weights[1]/(class_weights[0]+class_weights[1]))]
    
classifiers = [GaussianNB(),
               KNeighborsClassifier(n_jobs=-1, n_neighbors=3), # n_jobs = -1 uses all cores, for n core(s) = n
               #LinearDiscriminantAnalysis(solver='svd',priors=priors), # No tiene random_state
               #SVC(kernel="linear",random_state=seed,gamma='scale',class_weight=class_weights),
               #SVC(kernel = 'rbf', random_state=seed,gamma='scale',class_weight=class_weights),
               #LogisticRegression(solver='lbfgs',random_state=seed,class_weight=class_weights), 
               #MLPClassifier(hidden_layer_sizes= (20), random_state = seed, max_iter=50000, shuffle=False), # Neurons should be at least 25 (number of items we work with)
               DecisionTreeClassifier(random_state = seed,class_weight=class_weights), # Only 1 tree
               RandomForestClassifier(n_estimators=100,n_jobs=-1,random_state=seed,class_weight=class_weights), 
               #GradientBoostingClassifier(random_state=seed), 
               #AdaBoostClassifier(random_state = seed), 
               #BaggingClassifier(random_state=seed)
              ]


# Create a dataframe for the results with all ML statistics:
df_ML = pd.DataFrame(columns=['Method', 'ACC','AUROC' ,'precision' ,'recall' ,'f1-score' ])

# Fit each classifier:
for cls in classifiers:
    print("\n***", cls)
    ACC,AUROC,precision,recall,f1score=ML_baseline(cls, X_tr_norm, y_tr_norm, X_ts_norm, y_ts_norm, seed=seed)
    df_ML = df_ML.append({'Method': str(type(cls).__name__),
                          'ACC': float(ACC),
                          'AUROC': float(AUROC),
                          'precision': float(precision),
                          'recall': float(recall),
                          'f1-score': float(f1score)}, ignore_index=True)

df_ML

# Save the results as CSV file:
df_ML.to_csv(r'results/ML_statistics.csv')