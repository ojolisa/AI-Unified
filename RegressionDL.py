import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Conv2D, Flatten, LSTM, Attention, Input
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import requests
import os
import uuid

class RegressionDL:
    def __init__(self, dataset_url, hasChanged, task, mainType, archType, architecture, hyperparameters):
        self.dataset_url = dataset_url
        self.archType = archType
        self.mainType = mainType
        self.architecture = architecture
        self.hasChanged = hasChanged
        self.hyperparameters = hyperparameters
        self.data, self.target_col = self.load_and_prepare_data()
        self.task_type = task
        self.model = None
        self.scaler = StandardScaler()
        self.model_file_path = 'model.h5'
        self.scaler_file_path = 'scaler.pkl'
        self.api_url = 'https://s3-api-uat.idesign.market/api/upload'
        self.bucket_name = 'idesign-quotation'

    def load_and_prepare_data(self):
        df = pd.read_csv(self.dataset_url)
        target_col = df.columns[-1]  
        for column_name in df.columns:
            unique_values = df[column_name].nunique()

            if unique_values <= 4 and df[column_name].dtype in ['object', 'string']:
                dummies = pd.get_dummies(df[column_name], prefix=column_name)
                df = pd.concat([df, dummies], axis=1)
                df = df.drop(columns=[column_name])
                print(f"Dummies created for column '{column_name}'.")

        string_columns = df.select_dtypes(include=['object']).columns
        df = df.drop(columns=string_columns)
        return df, target_col

    def determine_task_type(self):
        target_values = self.data[self.target_col]
        unique_values = set(target_values)
        if len(unique_values) / len(self.data) > 0.1:
            return 'regression'
        else:
            return 'classification'

    def build_model(self):
        input_shape = (self.data.shape[1] - 1,)
        if self.archType == 'default':
            self.build_dense_model(input_shape)
        # elif self.archType == '4':
        #     self.build_cnn_model(input_shape)
        # elif self.archType == '5':
        #     self.build_lstm_model(input_shape)
        # elif self.archType == '6':
        #     self.build_attention_model(input_shape)
        else:
            raise ValueError("Unsupported model type. Choose from 'dense', 'cnn', 'lstm', 'attention'.")
        
    def build_dense_model(self, input_shape, layers=[64, 32], activation='relu', output_activation=None):
        model = Sequential()
        model.add(Dense(layers[0], input_shape=input_shape, activation=activation))
        for layer in layers[1:]:
            model.add(Dense(layer, activation=activation))
        if self.task_type == 'regression':
            model.add(Dense(1, activation=output_activation))
        else:
            model.add(Dense(len(np.unique(self.data[self.target_col])), activation='softmax'))
        self.model = model
        return model

    # def build_cnn_model(self, input_shape, conv_layers=[(32, (3, 3)), (64, (3, 3))], dense_layers=[64], activation='relu', output_activation=None):
    #     model = Sequential()
    #     model.add(Input(shape=input_shape))
    #     for filters, kernel_size in conv_layers:
    #         model.add(Conv2D(filters, kernel_size, activation=activation))
    #     model.add(Flatten())
    #     for layer in dense_layers:
    #         model.add(Dense(layer, activation=activation))
    #     if self.task_type == 'regression':
    #         model.add(Dense(1, activation=output_activation))
    #     else:
    #         model.add(Dense(len(np.unique(self.data[self.target_col])), activation='softmax'))
    #     self.model = model
    #     return model

    # def build_lstm_model(self, input_shape, lstm_units=50, dense_layers=[64], activation='relu', output_activation=None):
    #     model = Sequential()
    #     model.add(LSTM(lstm_units, input_shape=input_shape, activation=activation))
    #     for layer in dense_layers:
    #         model.add(Dense(layer, activation=activation))
    #     if self.task_type == 'regression':
    #         model.add(Dense(1, activation=output_activation))
    #     else:
    #         model.add(Dense(len(np.unique(self.data[self.target_col])), activation='softmax'))
    #     self.model = model
    #     return model

    # def build_attention_model(self, input_shape, attention_units=50, dense_layers=[64], activation='relu', output_activation=None):
    #     inputs = Input(shape=input_shape)
    #     attention = Attention()([inputs, inputs])
    #     flatten = Flatten()(attention)
    #     x = flatten
    #     for layer in dense_layers:
    #         x = Dense(layer, activation=activation)(x)
    #     if self.task_type == 'regression':
    #         outputs = Dense(1, activation=output_activation)(x)
    #     else:
    #         outputs = Dense(len(np.unique(self.data[self.target_col])), activation='softmax')(x)
    #     model = tf.keras.Model(inputs, outputs)
    #     self.model = model
    #     return model

    def compile_and_train(self):
        if not self.model:
            raise ValueError("Model is not defined. Please build a model first.")
        
        optimizer = self.hyperparameters.get('optimizer', 'adam')
        epochs = self.hyperparameters.get('epochs', 10)
        batch_size = self.hyperparameters.get('batch_size', 32)

        if self.task_type == 'regression':
            loss = 'mean_squared_error'
            metrics = []
        else:
            loss = 'sparse_categorical_crossentropy'
            metrics = ['accuracy']
        
        self.model.compile(optimizer=optimizer, loss=loss, metrics=metrics)
        X = self.data.drop(columns=[self.target_col])
        y = self.data[self.target_col]

        if self.task_type == 'regression':
            X = self.scaler.fit_transform(X)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.history = self.model.fit(X_train, y_train, validation_data=(X_test, y_test), epochs=epochs, batch_size=batch_size, callbacks=[EarlyStopping(patience=3)])
        self.X_test, self.y_test = X_test, y_test

    def evaluate_model(self):
        results = self.model.evaluate(self.X_test, self.y_test, verbose=0)
        print(f"Evaluation results: {results}")
        return results

    def save_model(self):
        self.model.save(self.model_file_path)
        joblib.dump(self.scaler, self.scaler_file_path)
        print(f"Model saved to {self.model_file_path}")
        print(f"Scaler saved to {self.scaler_file_path}")

    def upload_files_to_api(self):
        try:
            files = {
                'bucketName': (None, self.bucket_name),
                'files': open(self.model_file_path, 'rb')
            }
            response_model = requests.put(self.api_url, files=files)
            response_data_model = response_model.json()
            model_url = response_data_model.get('locations', [])[0] if response_model.status_code == 200 else None

            if model_url:
                print(f"Model uploaded successfully. URL: {model_url}")
            else:
                print(f"Failed to upload model. Error: {response_data_model.get('error')}")
                return None, None

            files = {
                'bucketName': (None, self.bucket_name),
                'files': open(self.scaler_file_path, 'rb')
            }
            response_scaler = requests.put(self.api_url, files=files)
            response_data_scaler = response_scaler.json()
            scaler_url = response_data_scaler.get('locations', [])[0] if response_scaler.status_code == 200 else None

            if scaler_url:
                print(f"Scaler uploaded successfully. URL: {scaler_url}")
            else:
                print(f"Failed to upload scaler. Error: {response_data_scaler.get('error')}")
                return model_url, None

            return model_url, scaler_url

        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {str(e)}")
            return None, None

    def execute(self):
        self.build_model()
        self.compile_and_train()
        self.evaluate_model()
        self.save_model()
        model_url, scaler_url = self.upload_files_to_api()
        if model_url and scaler_url:
            _id = str(uuid.uuid4())
            model_obj = {
                "modelUrl": model_url,
                "size": os.path.getsize(self.model_file_path) / (1024 ** 3),
                "id": _id,
                "helpers": [{"scaler": scaler_url}],
                "modelArch": self.architecture,
                "hyperparameters": self.hyperparameters
            }
            return model_obj
        else:
            return None

