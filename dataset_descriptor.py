import numpy as np
from inflection import pluralize

from ontology import EmbeddedClassTree, tree_score
from dataset import EmbeddedDataset
from embedding import Embedding
from utils import mean_of_rows, no_op


class DatasetDescriptor():

    def __init__(self, 
        dataset='data/185_baseball.csv',
        ontology='ontologies/dbpedia_2016-10.nt',
        embedding='models/wiki2vec/en.model',
        row_agg_func=mean_of_rows,
        tree_agg_func=np.mean,
        source_agg_func=mean_of_rows,
        max_num_samples=1e6,
        verbose=False,
        ):

        # print function that works only when verbose is true
        self.vprint = print if verbose else no_op
        self.max_num_samples = max_num_samples

        self.embedding = embedding if isinstance(embedding, Embedding) else Embedding(embedding_path=embedding, verbose=verbose)
        self.dataset = dataset if isinstance(dataset, EmbeddedDataset) else EmbeddedDataset(self.embedding, dataset_path=dataset, verbose=verbose)
        self.tree = ontology if isinstance(ontology, EmbeddedClassTree) else EmbeddedClassTree(self.embedding, tree_path=ontology, verbose=verbose)

        self.row_agg_func = row_agg_func
        self.source_agg_func = source_agg_func
        self.tree_agg_func = tree_agg_func

        self.similarity_matrices = {}

    @property
    def classes(self):
        return self.tree.classes

    def sources(self):
        return list(self.similarity_matrices.keys())
    
    
    def compute_similarity_matrices(self, reset_matrices=True):

        class_matrix = self.tree.class_vectors.T

        # compute cosine similarity bt embedded data and ontology classes for each source
        for src, data_matrix in self.dataset.data_vectors.items():

            self.vprint('computing class similarity for data from:', src)
            
            sim_mat = np.dot(data_matrix, class_matrix)

            if reset_matrices or not self.similarity_matrices.get(src):
                self.similarity_matrices[src] = sim_mat
            else:
                self.similarity_matrices[src] = np.vstack([self.similarity_matrices[src], sim_mat])


    def get_dataset_class_scores(self):

        if not self.similarity_matrices:
            self.vprint('computing similarity matrices')
            self.compute_similarity_matrices()

        sources = self.sources()

        self.vprint('aggregating row scores')
        sim_scores = {src: self.row_agg_func(self.similarity_matrices[src]) for src in sources}
        
        self.vprint('aggregating tree scores')
        tree_scores = {src: self.aggregate_tree_scores(sim_scores[src]) for src in sources}
        
        self.vprint('aggregating source scores')
        return self.aggregate_source_scores(tree_scores)

    
    def get_dataset_description(self):

        final_scores = self.get_dataset_class_scores()
        top_word = self.tree.classes[np.argmax(final_scores)]
        description = 'This dataset is about {0}.'.format(pluralize(top_word))
        self.vprint('\n\n dataset description:', description, '\n\n')

        return(description)
        

    def aggregate_tree_scores(self, scores):
        # convert score to dict that maps class to score if needed
        score_map = scores if isinstance(scores, dict) else dict(zip(self.tree.classes, scores))
        
        # aggregate score over tree structure
        agg_score_map = tree_score(score_map, self.tree, self.tree_agg_func)
        
        # convert returned score map back to array
        return np.array([agg_score_map[cl] for cl in self.tree.classes]) 


    def aggregate_source_scores(self, scores):
        assert len(scores) == len(self.sources())
        if isinstance(scores, dict):
            scores = list(scores.values())                
        return self.source_agg_func(scores)
