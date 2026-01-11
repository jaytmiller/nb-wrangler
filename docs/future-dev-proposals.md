# nb-wrangler: Future Development Roadmap

## 1. Vision and Strategy

**Vision:** To make notebook environment management seamless, reproducible, and accessible to all users, from individual curators to large teams.

**Core Strategy:** We are shifting from a "Plan A" model (monolithic, curator-built container images) to a more flexible "Plan B" model. This new model focuses on **pre-installed, centrally managed libraries ("pantries") of versioned, installable kernels and data.** `nb-wrangler` will be the primary tool for creating, managing, and deploying these assets into user environments like JupyterLab.

**Guiding Principle:** User adoption is our primary measure of success. New features must be balanced against the need to train, support, and engage with our users. Every feature should aim to lower the barrier to entry and make `nb-wrangler` more intuitive.

---

## 2. Priority 0: Foundational Work

*These tasks are critical for stability, maintainability, and growing the development team. They must be addressed before or in parallel with any new feature work.*

- **Implement Comprehensive Unit Tests:** Create a robust test suite covering the core logic of `nb-wrangler`. This is non-negotiable for enabling broader team involvement and ensuring future changes don't introduce regressions.
- **Engage Curators and Admins:**
    - **Curator Tutorial:** Conduct hands-on training for curators (e.g., Rossy, Tyler, Thomas) on creating specs and managing environments.
    - **Admin/Installer Tutorial:** Conduct training for admins (e.g., Octarine) on installing and managing shared `nb-wrangler` environments.
    - **Feedback Loop:** Establish a clear process for soliciting and incorporating feedback from these sessions into our development priorities.
- **Productionize a Key Use-Case:**
    - Fully resolve environment installation within the Octarine platform.
    - Set up the `roman-20` environment as an unpackable, "Plan B" style kernel in the Roman OPS environment. This serves as a real-world validation of our strategy.

---

## 3. Priority 1: Core Experience and Usability

*These features will significantly improve the day-to-day experience of using `nb-wrangler` and are essential for wider adoption.*

- **Polish Kernel Management:**
    - Refine the kernel packing and unpacking process to use a formal, robust `mamba` workflow instead of relying on `micromamba` internals.
    - Improve idempotency: ensure re-running an installation doesn't cause errors (e.g., `conda` kernel redefinition issues).
- **Flexible Environment Management (`NBW_PATH`):**
    - Implement a `PATH`-like mechanism (`NBW_PATH`) for discovering multiple pantries.
    - Support an arbitrary number of pantries with a clear priority order (e.g., user-defined > team-shared > system-wide).
- **Improved CLI and Terminal Integration:**
    - Finalize the command-line syntax for selecting kernels/specs from pantries.
    - Ensure per-kernel environment variables are correctly activated in terminal sessions, not just notebooks, for a consistent user experience.
- **On-Platform Integration Tests:** Write tests that run on the target platform to verify that switching between different pantry configurations (system, team, user) works as expected.

---

## 4. Priority 2: Game-Changer Features

*These are larger initiatives that could fundamentally change how users interact with `nb-wrangler` and the notebook ecosystem.*

- **JupyterLab Extension:**
    - **Vision:** Create a GUI within JupyterLab for managing `nb-wrangler` environments.
    - **Features:**
        - Browse available pantries and kernels.
        - Install/unpack kernels with a single click.
        - Select a kernel for a notebook or terminal.
        - Potentially, a GUI for creating or editing simple specs.
    - **Impact:** This would make `nb-wrangler` accessible to users who are not comfortable with the command line, dramatically increasing adoption.
- **Decouple and Simplify Specs:**
    - Generalize specs to be independent of notebook repositories.
    - Introduce simplified spec types for common use cases:
        - `environment-only`: Defines a Conda/pip environment.
        - `data-only`: Defines a set of data to be downloaded/installed.
        - `notebooks-only`: Defines a collection of notebooks.
    - **Impact:** Lowers the barrier to entry and makes `nb-wrangler` a more versatile, composable tool.
- **Interactive Spec Curation (`nb-wrangler init`):**
    - Create a new interactive command (`nb-wrangler init`) that guides a user through creating a `spec.yaml` file by asking a series of questions.
    - **Impact:** Drastically simplifies the process of getting started for new users.

---

## 5. Priority 3: Future Architecture and Ecosystem

*Long-term ideas for expanding the capabilities and interoperability of `nb-wrangler`.*

- **Lightweight Generic Base Image:** Create a minimal base container image that contains only `nb-wrangler` and its dependencies. Kernels and data would then be installed into this image at runtime, fully embracing the "Plan B" model.
- **Generalized Pantry Structure:** Adapt the pantry organization so it can store and describe environments, data, and notebooks, even without a `wrangler` spec. This would allow interoperability with other tools.
- **Robust Secrets Management:** Design and implement a secure way to handle secrets (e.g., Git tokens) needed for curation, avoiding hardcoded PATs. Explore integration with environment variables or managed secret stores.
- **Web Dashboard:** A potential standalone web application to visualize the contents of all known pantries, build statuses, test reports, and environment metadata.

---

## 6. Appendix: Plan A Maintenance

*While our primary focus is the "Plan B" strategy, we may need to continue maintaining the existing "Plan A" (curator-built images) workflow.*

- **Secure and Finalize Builds:** Fix remaining issues with curator-driven image builds and GitHub hosting. Work with ITSD/CCOE on security scanning and release processes.
- **Enhance Build Automation:** Explore automatic PR creation for SPI-injected builds to speed up iteration for developers who opt-in.

---

## 7. A Straw-man Framework for Execution

*The following is a proposal to kickstart discussion on how we can execute this roadmap as a team. The ideas, task assignments, and estimates are suggestions, and every team member should feel empowered to challenge them and contribute to the final plan.*

### Onboarding New Team Members

To effectively involve more of our scrum team, we should identify starter tasks that are self-contained, high-value, and provide a good learning opportunity.

- **Phase 1: Learning the Codebase.** The single best initial task for a new contributor is **implementing unit tests**. By writing tests for an existing module (e.g., `compiler.py`, `data_manager.py`), a developer can learn a specific part of the system in-depth without the risk of breaking production features. This work can be easily parallelized across multiple team members.

- **Phase 2: Contributing to Features.** Once a developer is comfortable with a module, they can take on a small, well-defined feature. Good candidates from this roadmap include **Flexible Environment Management (`NBW_PATH`)** or tasks within **Improved CLI and Terminal Integration**.

### AI-Accelerated Development

We can significantly accelerate development by pairing human developers with AI. The following task types are prime candidates for this "pilot/co-pilot" approach:

- **Unit Testing:** AI can generate the complete boilerplate for test files, including mocks and varied test cases, leaving the developer to focus on the core logic.
- **Scaffolding New Components:** For major features like the **JupyterLab Extension** or the **Web Dashboard**, AI can generate the entire initial project structure, build scripts, and basic UI components in minutes.
- **Interactive Wizards and CLIs:** The logic for interactive command-line tools (e.g., `nb-wrangler init`) is pattern-based and ideal for AI generation.

### Preliminary Effort Estimates

The following estimates are intended to gauge the relative size of each task and facilitate planning conversations. They use a Fibonacci-like scale where **1** is a few days, **3** is a few weeks, and **5** is one or more months of work.

#### **Priority 0: Foundational Work**
- Implement Comprehensive Unit Tests: **(3/5)**
- Engage Curators and Admins (tutorials, feedback loop): **(2/5)**
- Productionize a Key Use-Case (Octarine/Roman OPS): **(3/5)**

#### **Priority 1: Core Experience and Usability**
- Polish Kernel Management (formal mamba, idempotency): **(2/5)**
- Flexible Environment Management (`NBW_PATH`): **(1/5)**
- Improved CLI and Terminal Integration: **(1/5)**
- On-Platform Integration Tests: **(2/5)**

#### **Priority 2: Game-Changer Features**
- JupyterLab Extension: **(5/5)**
- Decouple and Simplify Specs: **(3/5)**
- Interactive Spec Curation (`nb-wrangler init`): **(2/5)**

#### **Priority 3: Future Architecture and Ecosystem**
- Lightweight Generic Base Image: **(1/5)**
- Generalized Pantry Structure: **(3/5)**
- Robust Secrets Management: **(2/5)**
- Web Dashboard: **(5/5)**

#### **Appendix: Plan A Maintenance**
- Secure and Finalize Builds: **(2/5)**
- Enhance Build Automation: **(1/5)**
