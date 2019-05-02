import glob
import os
from EnsemblePursuit import EnsemblePursuitPyTorch
from scipy.io import loadmat
import numpy as np
from sklearn.linear_model import ridge_regression
import scipy.io as sio
import torch
import matplotlib.pyplot as plt
from sklearn.linear_model import ridge_regression
from scipy import io
from scipy.sparse.linalg import eigsh
from utils import test_train_split, evaluate_model_torch, subtract_spont, corrcoef, PCA
from sklearn.decomposition import SparsePCA
import pandas as pd
from scipy import stats
import matplotlib.gridspec as gridspec

class ModelPipeline():
    def __init__(self,data_path, save_path, model,nr_of_components,init_method=None,lambdas=None, alphas=None):
        self.data_path=data_path
        self.save_path=save_path
        self.model=model
        self.lambdas=lambdas
        self.alphas=alphas
        self.nr_of_components=nr_of_components
        self.init_method=init_method
        
    def fit_model(self):
        for filename in glob.glob(os.path.join(self.data_path, '*MP034_2017-09-11.mat')):
            print(filename[45:85])
            data = io.loadmat(filename)
            resp = data['stim'][0]['resp'][0]
            spont =data['stim'][0]['spont'][0]
            if self.model=='EnsemblePursuit':
                X=subtract_spont(spont,resp)
                for lambd_ in self.lambdas:
                    neuron_init_dict={'method':self.init_method,'parameters':{'n_av_neurons':100,'T':10,'n_of_neurons':1,'min_assembly_size':8}}
                    print(str(neuron_init_dict['parameters']['n_av_neurons']))
                    ep=EnsemblePursuitPyTorch()
                    U_V,nr_of_neurons,U,V, cost_lst,seed_neurons,ensemble_neuron_lst=ep.fit_transform(X,lambd_,self.nr_of_components,neuron_init_dict)
                    np.save(self.save_path+filename[45:85]+'_n_av_n_'+str(neuron_init_dict['parameters']['n_av_neurons'])+'_'+str(lambd_)+'_'+str(self.nr_of_components)+'_V_ep.npy',V)
                    np.save(self.save_path+filename[45:85]+'_n_av_n_'+str(neuron_init_dict['parameters']['n_av_neurons'])+'_'+str(lambd_)+'_'+str(self.nr_of_components)+'_U_ep.npy',U)
                    np.save(self.save_path+filename[45:85]+'_n_av_n_'+str(neuron_init_dict['parameters']['n_av_neurons'])+'_'+str(lambd_)+'_'+str(self.nr_of_components)+'_cost_ep.npy',cost_lst)
                    np.save(self.save_path+filename[45:85]+'_n_av_n_'+str(neuron_init_dict['parameters']['n_av_neurons'])+'_'+str(lambd_)+'_'+str(self.nr_of_components)+'_n_neurons_ep.npy',nr_of_neurons)
                    np.save(self.save_path+filename[45:85]+'_n_av_n_'+str(neuron_init_dict['parameters']['n_av_neurons'])+'_'+str(lambd_)+'_'+str(self.nr_of_components)+'_ensemble_neuron_lst.npy',ensemble_neuron_lst)
            if self.model=='SparsePCA':
                X=subtract_spont(spont,resp)
                X=stats.zscore(X)
                print(X.shape)
                for alpha in self.alphas:
                    sPCA=SparsePCA(n_components=self.nr_of_components,alpha=alpha,random_state=7, max_iter=100, n_jobs=-1,verbose=1)
                    #X=X.T
                    model=sPCA.fit(X)
                    U=model.components_
                    print('U',U.shape)
                    #errors=model.error_
                    V=sPCA.transform(X)
                    print('V',V.shape)
                    np.save(self.save_path+filename[45:85]+'_'+str(alpha)+'_'+str(self.nr_of_components)+'_U_sPCA.npy',U)
                    np.save(self.save_path+filename[45:85]+'_'+str(alpha)+'_'+str(self.nr_of_components)+'_V_sPCA.npy',V)
                    #np.save(self.save_path+filename[45:85]+'_'+str(alpha)+'_'+str(self.nr_of_components)+'_errors_sPCA.npy',errors)

    def knn(self):
        if self.model=='SparsePCA':
             columns=['Mouse','alpha','accuracy']
             acc_df=pd.DataFrame(columns=columns)
             for filename in glob.glob(os.path.join(self.save_path, '*V_sPCA.npy')):
                V=np.load(filename)
                #print(self.data_path+'/'+filename[43:78]+'.mat')
                istim=sio.loadmat(self.data_path+'/'+filename[43:78]+'.mat')['stim']['istim'][0][0].astype(np.int32)
                istim -= 1 # get out of MATLAB convention
                istim = istim[:,0]
                nimg = istim.max() # these are blank stims (exclude them)
                V = V[istim<nimg, :]
                istim = istim[istim<nimg]
                x_train,x_test,y_train,y_test=test_train_split(V,istim)
                acc=evaluate_model_torch(x_train,x_test)
                acc_df=acc_df.append({'Mouse':filename[43:78],'alpha':filename[83:89],'accuracy':acc},ignore_index=True)
             print(acc_df)

    def check_sparsity(self):
        if self.model=='SparsePCA':
            model_string='*U_sPCA.npy'
        if self.model=='EnsemblePursuit':
            model_string='*U_ep.npy'
        for filename in glob.glob(os.path.join(self.save_path, model_string)):
            print(filename)
            U=np.load(filename)
            print(U.shape)
            prop_lst=[]
            for j in range(0,150):
                proportion_of_nonzeros=np.sum(U[j,:]!=0)/U.shape[1]
                #print(proportion_of_nonzeros)
                prop_lst.append(proportion_of_nonzeros)
            plt.hist(prop_lst)
            plt.show()
                        
              
    def compute_final_error(self):
        if self.model=='SparsePCA':
            for filename_V in glob.glob(os.path.join(self.save_path, '*V_sPCA.npy')):
                for filename_U in glob.glob(os.path.join(self.save_path, '*U_sPCA.npy')):
                    if filename_V[:-10]==filename_U[:-10]:
                         U=np.load(filename_U)
                         V=np.load(filename_V)
                         data = io.loadmat(self.data_path+'/'+filename_V[43:78]+'.mat')
                         resp = data['stim'][0]['resp'][0]
                         spont = data['stim'][0]['spont'][0]
                         X=subtract_spont(spont,resp)
                         #print(X.shape)
                         X=stats.zscore(X,axis=0)
                         residuals_squared=np.mean((X-(U.T@V.T).T)*(X-(U.T@V.T).T))
                         U_V=(U.T@V.T).T
                         #plt.hist(U_V, range=(-10,10))
                         #plt.show()
                         #plt.hist(X.flatten(),range=(-10,10))
                         plt.plot(range(0,100),X[:100,0])
                         plt.plot(range(0,100),U_V[:100,0])
                         plt.legend(('X','U_V'))
                         plt.show()
                         print(residuals_squared)
                         print('corrcoef',np.corrcoef(X[:,0],U_V[:,0]))
    
    def fit_ridge(self):
        images=sio.loadmat(self.data_path+'/images_natimg2800_all.mat')['imgs']
        images=images.transpose((2,0,1))
        images=images.reshape((2800,68*270))
        reduced_images=PCA(images)
        if self.model=='EnsemblePursuit':
            model_string='*V_ep.npy'
        if self.model=='SparsePCA':
            model_string='*V_sPCA.npy'
        for filename in glob.glob(os.path.join(self.save_path, model_string)):
            print(filename)
            stim=sio.loadmat(self.data_path+'/'+filename[43:78]+'.mat')['stim']['istim'][0][0]
            #test train split
            components=np.load(filename)
            x_train,x_test,y_train,y_test=test_train_split(components,stim)
            y_train=y_train-1
            reduced_images_=reduced_images[y_train]
            for alpha in [5000,10000,15000, 20000, 30000]:
                assembly_array=[] 
                for assembly in range(0,self.nr_of_components):
                    av_resp=(x_train[:,assembly].T+x_test[:,assembly].T)/2
                    reg=ridge_regression(reduced_images_,av_resp,alpha=alpha)
                    assembly_array.append(reg)
                assembly_array=np.array(assembly_array) 
                if self.model=='EnsemblePursuit':
                    file_string=filename[:-11]+'_'+str(alpha)+'_ep_reg.npy'
                if self.model=='SparsePCA':      
                    file_string=filename[:-11]+'_'+str(alpha)+'_sPCA_reg.npy'
                np.save(file_string,assembly_array)

    def plot_receptive_fields(self):
        if self.model=='SparsePCA':
            model_string='*sPCA_reg.npy'
        for filename in glob.glob(os.path.join(self.save_path, model_string)):
            print(filename)
            assembly_array=np.load(filename)
            fig = plt.figure(figsize=(20,20))
            fig.tight_layout()
            fig.subplots_adjust(hspace=0.0)
            for assembly in range(0,self.nr_of_components):
                reg=assembly_array[assembly,:].reshape(68,270)
                sub = fig.add_subplot(10,15,assembly+1)
                sub.imshow(reg)
                sub.set_xticks([])
                sub.set_yticks([])
            plt.show()

    def plot_receptive_fields2(self):
        if self.model=='SparsePCA':
            model_string='*sPCA_reg.npy'
        for filename in glob.glob(os.path.join(self.save_path, model_string)):
            print(filename)
            assembly_array=np.load(filename)
            assembly_array=assembly_array.reshape(10,15,18360)
            #print(assembly_array.shape)
            fig=plt.figure(figsize=(10,15))
            for assembly in range(0,self.nr_of_components):
            	ax=fig.add_axes([1,1,0,0])
             
        
