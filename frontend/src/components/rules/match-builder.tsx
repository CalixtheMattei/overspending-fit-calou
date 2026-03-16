interface MatchBuilderProps {
    labelContains: string;
    onLabelContainsChange: (value: string) => void;
}

export const MatchBuilder = ({ labelContains, onLabelContainsChange }: MatchBuilderProps) => {
    return (
        <section className="space-y-3 rounded-xl border border-secondary bg-primary p-4">
            <div>
                <h3 className="text-sm font-semibold text-primary">When a transaction looks like this...</h3>
            </div>
            <div className="space-y-1">
                <label htmlFor="rule-match-label" className="text-xs font-medium text-secondary">
                    Label contains
                </label>
                <input
                    id="rule-match-label"
                    className="w-full rounded-md border border-secondary bg-primary px-3 py-2 text-sm text-primary"
                    placeholder='ex: "NETFLIX"'
                    value={labelContains}
                    onChange={(event) => onLabelContainsChange(event.target.value)}
                />
            </div>
        </section>
    );
};
