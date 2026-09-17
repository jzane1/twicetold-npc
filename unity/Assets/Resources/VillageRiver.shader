Shader "Twicetold/Village River"
{
    Properties { _BaseColor("Deep Water", Color) = (0.055,0.30,0.38,1) }
    SubShader
    {
        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" "Queue"="Geometry+10" }
        Pass
        {
            Tags { "LightMode"="UniversalForward" }
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile_fog
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            CBUFFER_START(UnityPerMaterial)
                half4 _BaseColor;
            CBUFFER_END
            struct Attributes { float4 positionOS : POSITION; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; half fog : TEXCOORD1; };
            Varyings Vert(Attributes input)
            {
                Varyings output;
                float3 world = TransformObjectToWorld(input.positionOS.xyz);
                world.y += sin(world.z * .8 + world.x * .6 + _Time.y * 1.8) * .022;
                output.positionWS = world;
                output.positionCS = TransformWorldToHClip(world);
                output.fog = ComputeFogFactor(output.positionCS.z);
                return output;
            }
            half4 Frag(Varyings input) : SV_Target
            {
                float2 p = input.positionWS.xz;
                float wave = sin(p.x * 2.4 + p.y * .6 + _Time.y * 1.5);
                float crossWave = cos(p.y * 3.6 - p.x * .5 - _Time.y * 2);
                float3 normal = normalize(float3(wave * .045, 1, crossWave * .06));
                float3 view = normalize(GetCameraPositionWS() - input.positionWS);
                float fresnel = pow(1 - saturate(dot(view, normal)), 3);
                float3 color = lerp(_BaseColor.rgb, float3(.39,.65,.72), fresnel * .8);
                color += (wave * crossWave * .5 + .5) * float3(.025,.055,.045);
                Light sun = GetMainLight();
                float specular = pow(saturate(dot(normal, normalize(view + sun.direction))), 160);
                color += sun.color * specular * .5;
                float riverCenter = 43 + sin(p.y * .075) * 2.1 + sin(p.y * .031 + 1.2) * 1.2;
                float bank = smoothstep(7.45, 8.15, abs(p.x - riverCenter));
                float foam = bank * smoothstep(.45, .83, sin(p.y * 2.5 + _Time.y * 1.2) * .5 + .5);
                color = lerp(color, float3(.70,.81,.71), foam * .55);
                return half4(MixFog(color, input.fog), 1);
            }
            ENDHLSL
        }
    }
}
