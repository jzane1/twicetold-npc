Shader "Twicetold/Village River"
{
    Properties { _BaseColor("Deep Water", Color) = (.045,.23,.27,1) }
    SubShader
    {
        Tags { "RenderType"="Transparent" "RenderPipeline"="UniversalPipeline" "Queue"="Transparent" }
        Pass
        {
            Tags { "LightMode"="UniversalForward" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile_fog
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"
            CBUFFER_START(UnityPerMaterial)
                half4 _BaseColor;
            CBUFFER_END
            struct A { float4 p:POSITION; };
            struct V { float4 p:SV_POSITION; float3 world:TEXCOORD0; half fog:TEXCOORD1; float4 screen:TEXCOORD2; float eye:TEXCOORD3; };
            float hash(float2 p) {return frac(sin(dot(p,float2(127.1,311.7)))*43758.5453);}
            float noise(float2 p) {float2 i=floor(p),f=frac(p);f=f*f*(3-2*f);return lerp(lerp(hash(i),hash(i+float2(1,0)),f.x),lerp(hash(i+float2(0,1)),hash(i+1),f.x),f.y);}
            V Vert(A i)
            {
                V o;o.world=TransformObjectToWorld(i.p.xyz);
                o.world.y+=sin(o.world.z*.45+o.world.x*.7+_Time.y)*.013;
                o.p=TransformWorldToHClip(o.world);o.screen=ComputeScreenPos(o.p);o.eye=-TransformWorldToView(o.world).z;o.fog=ComputeFogFactor(o.p.z);return o;
            }
            half4 Frag(V i):SV_Target
            {
                float2 p=i.world.xz;
                float2 flow=p*float2(.7,.42)+float2(_Time.y*.025,-_Time.y*.12);
                float a=noise(flow), b=noise(flow*2.1+8.3);
                float3 normal=normalize(float3((a-.5)*.16,1,(b-.5)*.16));
                float3 view=normalize(GetCameraPositionWS()-i.world);
                float fresnel=pow(1-saturate(dot(view,normal)),4);
                float depth=LinearEyeDepth(SampleSceneDepth(i.screen.xy/i.screen.w),_ZBufferParams)-i.eye;
                float3 color=lerp(float3(.19,.44,.36),_BaseColor.rgb,saturate(depth*.55));
                color=lerp(color,float3(.44,.64,.70),fresnel*.73);
                Light sun=GetMainLight();
                color+=sun.color*pow(saturate(dot(normal,normalize(view+sun.direction))),210)*.4;
                float foam=(1-smoothstep(.025,.22,depth)) * smoothstep(.36,.68,noise(flow*3));
                float ripple=pow(saturate(sin((p.y*.55+p.x*.12+noise(flow)*2-_Time.y*.5)*6)),28);
                color+=ripple*.025;
                color=lerp(color,float3(.77,.86,.72),foam*.8);
                return half4(MixFog(color,i.fog),saturate(.7+depth*.25));
            }
            ENDHLSL
        }
    }
}
