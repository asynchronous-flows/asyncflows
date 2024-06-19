from asyncflows import Action, BaseModel


class Inputs(BaseModel):
    mutated_response_output: list
    expected_output: str


class Outputs(BaseModel):
    scores: list


class Score(Action[Inputs, Outputs]):
    name = "score"

    async def run(self, inputs: Inputs) -> Outputs:
        scores = []
        num_seeds = len(inputs.mutated_response_output) // 10

        for i in range(num_seeds):
            seed_scores = []
            for j in range(10):
                index = i * 10 + j
                mutated_output = inputs.mutated_response_output[index]
                score = self.calculate_score(mutated_output, inputs.expected_output)
                seed_scores.append(score)
            scores.append(sum(seed_scores) / len(seed_scores))

        return Outputs(scores=scores)

    def calculate_score(self, mutated_output: str, expected_output: str) -> float:
        # Implement your scoring logic here
        # Compare the mutated_output with the expected_output and return a score
        # You can use any scoring metric or algorithm of your choice
        # For example, you can use a simple equality check or a more sophisticated similarity measure
        if mutated_output == expected_output:
            return 1.0
        else:
            return 0.0
