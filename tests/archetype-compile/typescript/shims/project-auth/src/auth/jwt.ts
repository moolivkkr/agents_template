// HARNESS STUB: the project's JWT verifier that grpc-pattern-typescript.md's middleware imports.
export interface GrpcClaims {
  tenantId: string;
  userId: string;
  roles: string[];
}

export declare function validateJwt(token: string): Promise<GrpcClaims>;
