import torch
from torch import nn
from torch.autograd import Function, Variable
from .kernel import Kernel


class RBFFunction(Function):
    def __init__(self, x1, x2, eps=1e-5):
        if isinstance(x1, Variable):
            x1 = x1.data
        if isinstance(x2, Variable):
            x2 = x2.data
        self.x1 = x1
        self.x2 = x2
        self.eps = eps

    # Assumes log_lengthscale is a constant matrix (filled with
    # the parameter log_lengthscale) which is the size of the
    # resulting kernel matrix
    def forward(self, log_lengthscale):
        n, d = tuple(self.x1.size())
        m, _ = tuple(self.x2.size())

        res = self.x1.new(n, m).zero_()
        res.addmm_(1, 2, self.x1, self.x2.transpose(0, 1))  # res = 2 x1 x2^T

        x1_squared = torch.bmm(self.x1.view(n, 1, d), self.x1.view(n, d, 1))
        x1_squared = x1_squared.view(n, 1).expand(n, m)
        x2_squared = torch.bmm(self.x2.view(m, 1, d), self.x2.view(m, d, 1))
        x2_squared = x2_squared.view(1, m).expand(n, m)
        res.add_(-1, x1_squared).add_(-1, x2_squared)  # res = -(x - z)^2

        res.div_(log_lengthscale.exp() + self.eps)  # res = -(x - z)^2 / lengthscale
        res.exp_()

        self.save_for_backward(res)
        return res

    def backward(self, grad_output):
        kernel, = self.saved_tensors
        grad = kernel.log().mul_(-1).mul_(kernel)
        grad.mul_(grad_output.transpose(0, 1))
        return grad


class RBFKernel(Kernel):
    def __init__(self, log_lengthscale_bounds=(-10000, 10000), eps=1e-5):
        super(RBFKernel, self).__init__()
        self.eps = eps
        self.register_parameter('log_lengthscale', nn.Parameter(torch.zeros(1, 1)),
                                bounds=log_lengthscale_bounds)

    def forward(self, x1, x2):
        n, _ = x1.size()
        m, _ = x2.size()
        return RBFFunction(x1, x2, self.eps)(self.log_lengthscale.expand(n, m))
