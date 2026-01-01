export enum StageType {
    BETA = "beta",
    PROD = "prod",
}

export interface StageConfig {
    stageType: StageType;
    account: string;
    region: string;
}

export const DEFAULT_REGION = "us-east-1";
export const STAGES: StageConfig[] = [
    {
        stageType: StageType.BETA,
        account: "121846058771",
        region: DEFAULT_REGION,
    },
    {
        stageType: StageType.PROD,
        account: "946179427899",
        region: DEFAULT_REGION,
    },
];
