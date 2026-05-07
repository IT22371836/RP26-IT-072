# Component 4 - Bi-LSTM + CRF Training Explanation

This document explains the training notebook in simple English.

## What this notebook does

The notebook trains a model that reads review text and tags words with aspect labels such as quality, price, time, and communication.

The model has two main parts:
- **Bi-LSTM**: reads the sentence from left to right and right to left
- **CRF**: chooses the best tag sequence for the whole sentence

## Step-by-step explanation

### 1. Install dependencies

The notebook installs the Python libraries needed for training, such as TensorFlow, pandas, NumPy, matplotlib, seaborn, and scikit-learn.

It also prepares TensorFlow to use the GPU if one is available.

### 2. Load the dataset

The notebook loads an Excel file named `IOB_Annotated_Reviews_Dataset.xlsx`.

This file contains:
- words from review sentences
- IOB tags for each word
- sentiment labels

This is the data the model learns from.

### 3. Explore the data

The notebook prints basic dataset information and draws charts for:
- tag distribution
- sentiment distribution
- sentence length distribution

This helps you understand the dataset before training.

### 4. Build sequences and vocabularies

The notebook groups the data by sentence so each sentence becomes one training example.

Then it:
- converts words to lowercase
- builds a vocabulary for words
- builds a vocabulary for tags
- converts words and tags into numbers
- pads all sentences to the same length

This is needed because machine learning models work with numbers, not raw text.

### 5. Split the data

The data is split into:
- training set
- validation set
- test set

The training set is used to learn patterns.
The validation set is used to check progress during training.
The test set is used for final evaluation.

### 6. Define the CRF layer

The notebook creates a custom CRF layer in pure TensorFlow.

The CRF helps the model make better tagging decisions by looking at the full sequence of tags instead of predicting each word separately.

### 7. Build the Bi-LSTM + CRF model

The model contains these layers:
- **Embedding**: turns word IDs into vectors
- **Spatial Dropout**: reduces overfitting
- **Bidirectional LSTM**: reads the sentence in both directions
- **Dense layer**: produces tag scores
- **CRF layer**: selects the best final tag sequence

In simple terms, the model learns which words are important and how tags should follow each other.

### 8. Train the model

This is the main learning step.

For each epoch, the notebook:
- runs the training data through the model
- calculates the loss
- updates the weights
- checks the validation loss
- saves the best model weights
- reduces the learning rate if improvement slows down
- stops early if validation performance does not improve

In simple English:
- **epoch** = one full pass through the training data
- **loss** = how wrong the model is
- **early stopping** = stop when the model is no longer improving

### 9. Plot training curves

After training, the notebook plots training loss and validation loss.

This helps you see whether the model is learning well or overfitting.

### 10. Evaluate on the test set

The notebook loads the best saved weights and predicts tags for the test data.

Then it compares the predicted tags with the correct tags.

### 11. Generate reports

The notebook prints:
- precision
- recall
- F1-score
- classification report

It also computes aspect-level metrics for:
- QUAL
- PRICE
- TIME
- COMM

These metrics show how well the model detects each aspect category.

### 12. Create visualizations

The notebook creates several plots:
- confusion matrix
- aspect precision/recall/F1 chart
- heatmap of aspect metrics
- per-tag F1 chart
- inference heatmap for sample reviews

These charts help show where the model performs well and where it needs improvement.

### 13. Run inference on new reviews

The notebook defines a function that takes a new review, tokenizes it, converts words to numbers, runs the model, and returns predicted tags.

This is how the trained model is used on new text.

### 14. Save the trained model

At the end, the notebook saves:
- the model weights
- the model configuration
- the vocabulary file

These files let you reuse the model later without retraining.

## Short summary

The notebook trains a sequence tagging model for review analysis.

It learns from labeled sentences, predicts IOB tags for new reviews, and measures how well it detects each aspect type.

## One-line explanation

This notebook teaches a Bi-LSTM + CRF model to read review sentences and tag important words with aspect labels.