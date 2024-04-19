import math
import torch
from torch import nn
import torch.nn.functional as F


class LinearNet(nn.Module):
    def __init__(self, layer_sizes=[], leaky_relu_alpha = 0.2, dropout_p = 0, final_linear = False):
        super(LinearNet, self).__init__()
        self.final_linear = final_linear
        self.leaky_relu_alpha = leaky_relu_alpha
        self.dropout = nn.Dropout(p=dropout_p)
        
        self.net = nn.ModuleList()
        for i in range(len(layer_sizes) - 1):
            linear = nn.Linear(layer_sizes[i], layer_sizes[i + 1])
            
            self.net.append(linear)
        
    def forward(self, x):
        for i in range(len(self.net)):
            x = self.net[i](x)
            if i != len(self.net) - 1 or not self.final_linear:
                x = F.leaky_relu(x, negative_slope=self.leaky_relu_alpha)
                
            x = self.dropout(x)
        
        return x        

# Kind of useless since it would be slow to loop this but it's a good example of how to implement it
class Attention(nn.Module):
    def __init__(self, activation_function = torch.softmax):
        super(Attention, self).__init__()
        self.activation_function = activation_function
    
    def forward(self, Q, K, V):
        d = Q.size(-1)
        logits = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d)
        logits = self.activation_function(logits)
        return torch.matmul(logits, V)

class MAB(nn.Module):
    def __init__(self, embed_dim, num_heads, ff_layers = None, final_linear = True, activation_function = torch.softmax, layer_norm = False, dropout = 0.1):
        assert embed_dim % num_heads == 0, "Embedding dimension must be divisible by number of heads"
        
        super(MAB, self).__init__()
        self.activation_function = activation_function
        
        self.attention = nn.MultiheadAttention(embed_dim=embed_dim, num_heads=num_heads, batch_first=True)
        self.layer_norm = nn.LayerNorm(embed_dim) if layer_norm else None
        
        self.feedforward = LinearNet([embed_dim] + ff_layers + [embed_dim], final_linear=final_linear) 
        self.dropout = nn.Dropout(p=dropout)
    
    def forward(self, X, Y):
        attention = self.attention(X, Y, Y, need_weights=False)[0]
        H = X + attention
        
        if self.layer_norm:
            H = self.layer_norm(H)
        H = self.dropout(H)
        
        mab_out = H + self.feedforward(H)
        
        if self.layer_norm:
            mab_out = self.layer_norm(mab_out)
        mab_out = self.dropout(mab_out)
        
        return mab_out
    
class PMA(nn.Module):
    def __init__(self, embed_dims, seed_count, **mab_args):
        super(PMA, self).__init__()
        self.seed_count = seed_count
        
        self.mab = MAB(embed_dims, **mab_args)
        self.S = nn.Parameter(torch.empty(1, seed_count, embed_dims))
        nn.init.xavier_uniform_(self.S)
    
    def forward(self, X):
        return self.mab(self.S.repeat(X.size(0), 1, 1), X)

class ISAB(nn.Module):
    def __init__(self, m_induce, embed_dim, **mab_args):
        super(ISAB, self).__init__()
        
        self.m = m_induce
        self.mab1 = MAB(embed_dim, **mab_args)
        self.mab2 = MAB(embed_dim, **mab_args)
        self.I = nn.Parameter(torch.randn(self.m, embed_dim))
    
    def forward(self, X):
        H = self.mab1(self.I, X)
        return self.mab2(X, H)

class IPAB(nn.Module):
    def __init__(self, embed_dim, **mab_args):
        super(IPAB, self).__init__()
        self.embed_dim = embed_dim
        
        self.mab1 = MAB(embed_dim, **mab_args) 
        self.mab2 = MAB(embed_dim, **mab_args)
    
    def forward(self, X, Z):
        Z = self.mab1(Z.unsqueeze(1), X)
        return self.mab2(X, Z), Z.squeeze(1)

if __name__ == "__main__":
    # Test the layers
    net = LinearNet([10, 20, 30, 1])
    x = torch.randn(16,10)
    # print(net(x), net(x).shape)
    
    torch.manual_seed(0)
    ipab = IPAB(10, num_heads=2, ff_layers = [10,20,10])
    x = torch.ones(16, 30, 10)
    z = torch.ones(16, 10)
    print(ipab(x, z))
    