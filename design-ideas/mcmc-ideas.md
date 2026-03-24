# Making use of historic data for sprints

Some ideas for how to turn historic sprint data into a Monte Carlo forecasting model that captures both capacity and volatility. 

## Structure input data
For each past sprint  $i=1, \dots ,N$ , assemble a row in a table:

- Sprint identifier: $i$
- Team size: $n[i]$ (average people that sprint)
- Initial committed work: total story points committed at the start, $C[i]$
- Completed work: total story points completed, $X[i]$
- Spillover: story points that were not finished, $S[i]$
- Added work during sprint: in story points, $A[i]$
- Net throughput (optional derived): total completed regardless of when committed, e.g. $T[i]=X[i]$
- Change ratio (optional derived): $R[i]=A[i]/C[i]$ (scope added vs. initial commitment)
- Focus factor (optional derived): $F[i]=X[i]/(C[i]+A[i])$ fraction of total available work that actually got done
 
 These derived variables $(T[i],R[i],F[i])$ will make modeling simpler and more interpretable. 


## Decide what you want to forecast

Common questions you can address with Monte Carlo: 

- Single-sprint capacity: "How many story points are we likely to complete next sprint?"
- Multi-sprint delivery dates: "By when will we likely finish $B$ story points of backlog?"
- Risk to commitment: "If we commit to $C_{next}$ points, what is the probability of finishing them all?"

A good baseline is to model the distribution of throughput per sprint (and optionally per person) and the distribution of scope change, then simulate. 

## Baseline Monte Carlo model (non-parametric / empirical)

This is the simplest, robust approach and often outperforms over-engineered models for agile teams. 

### Throughput distribution

- Compute a normalized throughput, for example:- Throughput per person:  $t[i]=T[i]/n[i]$
- Collect the historical values $t[1],&hellip;,t[N]$
- Define the empirical distribution of throughput-per-person by treating each observed $t[i]$ as equally likely next sprint (or with more weight on recent sprints if the team is changing).
 
### Scope-change distribution

- Compute the ratio of added work per sprint: $R[i]=A[i]/C[i]$ (can be negative if work is removed).
- Again, use an empirical distribution over $R[i]$

 
### Simulating a single sprint 

To simulate one future sprint with team size $n_{future}$ and initial commitment $C_{future}$: 

1. Randomly draw a throughput-per-person sample $t^k4 from the historic set $\{t[i]\}$
2. Set simulated throughput for that sprint: $T^k   = t^k \times n_{future}$
3. Randomly draw a scope-change ratio $R^k$ from the historic set $\{R[i]\}$
4. Compute simulated added work: $A^k = R^k \times C_{future}$
5. Compute total work present in the sprint: $W^k = C_{future} + A$
6. Completed work is limited by capacity: $X^k = \textrm{min}(T^k, W^k)$
7. Spillover is then: $S^k = W^k - X^k$
8. Repeat steps 1–7 many times (e.g. 5,000–50,000 simulations). The resulting samples $X^k$ and $S^k$ give you the forecast distribution and volatility. 

#### Parametric Bayesian model (for more structure)
A statistical model can be defined and then use MCMC to sample from the posterior, a simple but useful choice is a hierarchical Bayesian model that explains throughput and scope change. 

### Throughput model
A common choice for count-like data with overdispersion is the negative binomial distribution.  For sprint $i$

- Let $T[i] = $ total completed story points that sprint.
- Model expected throughput as proportional to team size: $E[T[i]]=\lambda n[i]$, where $\lambda$ is the average story points completed per person per sprint.
- Then assume: $T[i]\approx \textrm{NegBin}(\mu=\lambda n[i], \phi)$, where $\phi$ is an overdispersion parameter capturing volatility. Place priors on $\lambda$ and $\phi$, for example: 
    -  $\lambda \approx \textrm{LogNormal}(m_{lambda},s_{lambda})$
    -  $\phi \approx \textrm{Half-Normal}(\sigma_{\phi})$
   Then use Markov Chain Monte Carlo to sample from the joint posterior $p(\lambda,\phi \verbatim{[1`:`N],n[1`:`N]})$


### Scope-change model
For the scope change ratio $R[i]=A[i]/C[i]$

If  $R[i]$ is often positive and skewed, a log-normal can work for $1+R[i]$ , $log[10](1+R[i]) \sdot \approx N(\mu_R,\sigma_R^2 )$
- Again, put priors on $\mu_R$ and $\sigma_R$ and use MCMC.
 
### Using the Bayesian model in simulation
Once you have MCMC samples of the parameters 

$$< \lambda^s   ,\psi^s;   ,\mu_R^s   ,\sigma_R^2 >$$

you can simulate future sprints by: 

1. Draw a parameter set from the posterior.
2. For given team size $n_{future}$ simulate throughput: $$T_{future} \textrm{NegBin}(\mu=\lambda^s   n_{future}, \psi^s   )$$
3. For a given commitment $C_{future}$ , simulate scope change ratio $$log[10](1+R_future) \approx N(\mu_R   ,({\sigma_R^s)^2 )$$ , then set $$ R_{future}=e^{log_{10}(1+R_{future})} - 1$$
4. Repeat the same logic as in Section 3.3 to compute completed work $X$ and spillover $S$ This combines parameter uncertainty (via MCMC) with process uncertainty (via simulation) and gives a full probabilistic picture of volatility. 
5. Incorporating Markov-chain "states". To explicitly use a Markov chain, you could introduce states that capture team conditions that change over time and affect throughput, for example:- State LowCapacity, Normal, HighCapacity based on actual people available, holidays, on-call duty.
- State HighChurn, MediumChurn, LowChurn based on how much work tends to be added mid-sprint.
 
Then:- Estimate state for each historic sprint (e.g., via thresholds on 
                              n[i]

 and 
                              R[i]

).
- Estimate transition probabilities between states: 
                  P(state[i+1]verbarstate[i])

.
- Condition your throughput and scope-change distributions on state, e.g. 
T[i]verbarstate[i]=s`~`NegBin(&#x3bc;=&#x3bb;[s]n[i],&#x3d5;[s])

.
- In simulation, you step the Markov chain to get the next state, then simulate throughput and scope change according to that state.
 This is useful when you know there are regimes (e.g., peak-vacation periods vs. normal periods) that change over time. 
6. Measuring volatility and capacity from the simulations
After you run the Monte Carlo simulations (with or without Bayesian parameter sampling), you can report:- Capacity distribution: quantiles of completed story points, e.g. 10th, 50th, 90th percentile of 
                               (k)
                              X   

.
- Spillover risk: for a given commitment 
                            C_future

, estimate 
                         Pr(X<C_future)

.
- Volatility: statistics of the simulated throughput and spillover, such as standard deviation, interquartile range, and probability of extreme low or high outcomes.
- Multi-sprint forecasts: roll the simulation forward sprint-by-sprint, updating remaining backlog and drawing new throughput and scope change each sprint.
 
7. Practical recommendation
For an agile team, I recommend this progression: -1. Start with the empirical, non-parametric Monte Carlo (Section 3). It is simple, uses your existing data directly, and is easy to explain to stakeholders.
 -1. If you want more rigor or need to extrapolate beyond existing team sizes/conditions, add the Bayesian negative-binomial model for throughput and a log-normal for scope change (Section 4) and run MCMC.
 -1. Only add an explicit Markov state model (Section 5) if you have clear, persistent regimes (like seasonal effects, structural team changes) and enough data per regime.
 
If you share a small anonymized slice of your historic data (a handful of sprints with the fields described above), I can help you instantiate one of these models numerically and outline the exact steps for Monte Carlo simulation. 





